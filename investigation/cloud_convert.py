"""Stream a GCS raw object once into auditable sharded Parquet."""
from __future__ import annotations
import argparse, hashlib, io, json, shutil, tempfile, time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from cloud_parallel_plan import Source, build_plan, list_sources
SCALE=1000000; VERSION=1
def key(x): return hashlib.blake2b(str(x).encode(),digest_size=16).hexdigest()
def scale(x,name):
    try: n=Decimal(str(x))*SCALE
    except Exception as e: raise ValueError("invalid %s: %r"%(name,x)) from e
    if not n.is_finite() or n!=n.to_integral_value(): raise ValueError("%s has nonzero precision beyond 1e-6: %r"%(name,x))
    return int(n)
def content(x):
    if isinstance(x,dict): return x
    if isinstance(x,str):
        try: x=json.loads(x)
        except json.JSONDecodeError:return None
        return x if isinstance(x,dict) else None
def base(c,s,o):
    m=c.get("market"); m=str(m) if isinstance(m,(str,int)) else None
    return dict(source_id=s,source_ordinal=o,event_timestamp_ms=c.get("timestamp"),market_id=m,market_key=key(m) if m else None)
def asset(x):
    x=str(x) if x is not None else None
    return dict(asset_id=x,asset_key=key(x) if x else None)
def rows(c,s,o):
    b=base(c,s,o); a=asset(c.get("asset_id")); t=c.get("event_type")
    if t=="price_change":
        return [("price_changes",dict(b,**asset(x.get("asset_id")),price_i=scale(x.get("price"),"price"),size_i=scale(x.get("size"),"size"),side=x.get("side"),best_bid_i=scale(x["best_bid"],"best_bid") if x.get("best_bid") is not None else None,best_ask_i=scale(x["best_ask"],"best_ask") if x.get("best_ask") is not None else None)) for x in c.get("price_changes",[]) if isinstance(x,dict)]
    if t=="last_trade_price": return [("trades",dict(b,**a,price_i=scale(c.get("price"),"price"),size_i=scale(c.get("size"),"size"),side=c.get("side"),fee_rate_bps=c.get("fee_rate_bps"),transaction_hash=c.get("transaction_hash")))]
    if t=="book":
        out=[("book_headers",dict(b,**a,book_hash=c.get("hash")))]
        for n,side in (("bids","BID"),("asks","ASK")):
            for x in c.get(n,[]):
                p,z=(x.get("price"),x.get("size")) if isinstance(x,dict) else (x[:2] if isinstance(x,(list,tuple)) and len(x)>=2 else (None,None))
                if p is not None: out.append(("book_levels",dict(b,**a,side=side,price_i=scale(p,"price"),size_i=scale(z,"size"))))
        return out
    if t=="tick_size_change": return [("tick_size_changes",dict(b,**a,old_tick_size_i=scale(c.get("old_tick_size"),"old_tick_size"),new_tick_size_i=scale(c.get("new_tick_size"),"new_tick_size")))]
    return [("other_feed_events",dict(b,event_type=t,payload_json=json.dumps(c,sort_keys=True,separators=(",",":"))))]
class Writer:
 def __init__(self,root,date,s,batch):
  self.root,self.date,self.s,self.batch=root,date,s,batch;self.b=defaultdict(list);self.parts=Counter();self.count=Counter()
 def add(self,t,r):
  mk=r.get("market_key"); shard="%02d"%(int(mk[:2],16)%64) if mk else "unknown"; k=(t,shard);self.b[k].append(r);self.count[t]+=1
  if len(self.b[k])>=self.batch:self.flush(k)
 def flush(self,k):
  if not self.b[k]:return
  import pyarrow as pa
  import pyarrow.parquet as pq
  t,sh=k;d=self.root/("table=%s/date=%s/market_shard=%s/source=%s"%(t,self.date,sh,self.s));d.mkdir(parents=True,exist_ok=True)
  pq.write_table(pa.Table.from_pylist(self.b[k]),d/("part-%05d.parquet"%self.parts[k]),compression="zstd",compression_level=3);self.parts[k]+=1;self.b[k].clear()
 def close(self):
  for k in list(self.b):self.flush(k)
def cname(run,s):return "runs/%s/completions/%s.json"%(run,s)
def complete(bucket,run,source,s):
 b=bucket.blob(cname(run,s))
 if not b.exists():return False
 try:x=json.loads(b.download_as_text())
 except Exception:return False
 return x.get("version")==VERSION and x.get("source")==asdict(source) and bool(x.get("files")) and all(bucket.blob(f["name"]).exists() and bucket.blob(f["name"]).size==f["bytes"] for f in x["files"])
def convert(source,raw,compact,run,stage_root,batch=50000):
 if source.kind!="regular_hour" or not source.date:raise ValueError("only classified regular hours are automatically scheduled")
 from google.cloud import storage
 import zstandard as zstd
 client=storage.Client();out=client.bucket(compact);s=key(source.uri);started=time.monotonic();last_report=started;print(json.dumps({"phase":"reading","source":source.uri}),flush=True)
 if complete(out,run,source,s):return {"source":source.uri,"status":"skipped_valid_completion"}
 stage=Path(tempfile.mkdtemp(prefix="poly-"+s[:10]+"-",dir=stage_root));w=Writer(stage,source.date,s,batch);stats=Counter();seen=set();dims={"markets":{},"assets":{}}
 try:
  name=source.uri.split("/",3)[3]
  with client.bucket(raw).blob(name).open("rb") as f, zstd.ZstdDecompressor().stream_reader(f) as z:
   for o,line in enumerate(io.TextIOWrapper(z,encoding="utf8",errors="replace"),1):
    if not line.strip():continue
    stats["outer_messages"]+=1
    if time.monotonic()-last_report >= 15:
     print(json.dumps({"phase":"reading","source":source.uri,"outer_messages":stats["outer_messages"],"unique_payloads":stats["unique_payloads"],"duplicates_skipped":stats["duplicates_skipped"],"elapsed_seconds":round(time.monotonic()-started,1)}),flush=True);last_report=time.monotonic()
    try:e=json.loads(line)
    except json.JSONDecodeError:w.add("non_feed_envelopes",dict(source_id=s,source_ordinal=o,reason="invalid_json"));continue
    if e.get("message_type")!="feed_message":stats["non_feed_envelopes"]+=1;w.add("non_feed_envelopes",dict(source_id=s,source_ordinal=o,message_type=e.get("message_type"),reason="non_feed"));continue
    c=content(e.get("content"))
    if c is None:stats["invalid_content"]+=1;w.add("invalid_content",dict(source_id=s,source_ordinal=o,reason="not_object"));continue
    fp=hashlib.blake2b(json.dumps(c,sort_keys=True,separators=(",",":")).encode(),digest_size=16).digest()
    if fp in seen:stats["duplicates_skipped"]+=1;continue
    seen.add(fp);stats["unique_payloads"]+=1;stats["event:"+str(c.get("event_type"))]+=1
    m=c.get("market")
    if isinstance(m,(str,int)):
     old=dims["markets"].setdefault(key(m),str(m))
     if old!=str(m):w.add("key_collisions",dict(source_id=s,dimension="market",stable_key=key(m),first_id=old,second_id=str(m)))
    for t,r in rows(c,s,o):
     w.add(t,r)
     if r.get("asset_key"):
      old=dims["assets"].setdefault(r["asset_key"],r["asset_id"])
      if old!=r["asset_id"]:w.add("key_collisions",dict(source_id=s,dimension="asset",stable_key=r["asset_key"],first_id=old,second_id=r["asset_id"]))
  for t,values in dims.items():
   kc,ic=("market_key","market_id") if t=="markets" else ("asset_key","asset_id")
   for k,v in values.items():w.add(t,dict(source_id=s,**{kc:k,ic:v}))
  w.close();files=[];print(json.dumps({"phase":"uploading","source":source.uri,"rows":dict(w.count),"elapsed_seconds":round(time.monotonic()-started,1)}),flush=True)
  for p in sorted(stage.rglob("*.parquet")):
   n="runs/%s/data/%s"%(run,p.relative_to(stage).as_posix());b=out.blob(n);b.upload_from_filename(str(p));files.append(dict(name=n,bytes=p.stat().st_size,md5_hash=b.md5_hash))
   if len(files)%20==0:print(json.dumps({"phase":"uploading","source":source.uri,"files_uploaded":len(files)}),flush=True)
  manifest=dict(version=VERSION,source=asdict(source),source_id=s,numeric_scale=SCALE,completed_at_utc=datetime.now(timezone.utc).isoformat(),stats=dict(stats),fact_rows=dict(w.count),files=files)
  print(json.dumps({"phase":"finalizing","source":source.uri,"files_uploaded":len(files),"elapsed_seconds":round(time.monotonic()-started,1)}),flush=True);b=out.blob(cname(run,s));b.upload_from_string(json.dumps(manifest,sort_keys=True),content_type="application/json")
  if json.loads(b.download_as_text())!=manifest:raise RuntimeError("completion manifest verification failed")
  return {"source":source.uri,"status":"completed","rows":dict(w.count)}
 finally:shutil.rmtree(stage,ignore_errors=True)
def main():
 p=argparse.ArgumentParser();p.add_argument("--raw-bucket",required=True);p.add_argument("--compact-bucket",required=True);p.add_argument("--run-id",required=True);p.add_argument("--staging-root",default="/tmp/poly-archive");p.add_argument("--batch-rows",type=int,default=50000);p.add_argument("--pilot-source");a=p.parse_args();Path(a.staging_root).mkdir(parents=True,exist_ok=True);sources=list_sources(a.raw_bucket)
 if a.pilot_source:
  found=[x for x in sources if x.uri==a.pilot_source]
  if len(found)!=1:raise ValueError("pilot source not found exactly once")
  print(json.dumps(convert(found[0],a.raw_bucket,a.compact_bucket,a.run_id,a.staging_root,a.batch_rows),sort_keys=True));return
 plan=build_plan(sources,4)
 from google.cloud import storage
 storage.Client().bucket(a.compact_bucket).blob("runs/%s/plan.json"%a.run_id).upload_from_string(json.dumps(plan,sort_keys=True,indent=2),content_type="application/json")
 work=[Source(**x) for q in plan["workers"] for x in q["sources"]]
 with ProcessPoolExecutor(max_workers=4) as pool:
  fs=[pool.submit(convert,x,a.raw_bucket,a.compact_bucket,a.run_id,a.staging_root,a.batch_rows) for x in work]
  for f in as_completed(fs):print(json.dumps(f.result(),sort_keys=True),flush=True)
if __name__=="__main__":main()
