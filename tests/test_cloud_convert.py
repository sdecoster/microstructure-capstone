from pathlib import Path
import sys
import pytest
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"investigation"))
from cloud_convert import SCALE,Writer,_scale_text,complete,fingerprint,parse_worker_indices,rows,scale
from cloud_parallel_plan import Source
def test_exact_scale_and_precision_rejection():
 assert scale("0.123456","price")==123456
 assert scale("1","size")==SCALE
 with pytest.raises(ValueError):scale("0.0000001","price")
def test_tick_size_is_preserved():
 assert rows({"event_type":"tick_size_change","market":"m","asset_id":"a","old_tick_size":"0.01","new_tick_size":"0.001"},"s",1)[0][1]["new_tick_size_i"]==1000
def test_other_event_is_audited():
 assert rows({"event_type":"unknown","market":"m"},"s",1)[0][0]=="other_feed_events"

def test_staged_writer_creates_parquet_part():
 with TemporaryDirectory() as temp:
  writer=Writer(Path(temp),'2026-08-16','source',1)
  writer.add('price_changes',{'market_key':'00','source_id':'source','price_i':1})
  writer.close()
  assert len(list(Path(temp).rglob('*.parquet')))==1

def test_exact_raw_payload_fingerprint_preserves_exact_dedupe_scope():
 assert fingerprint('{"a":1}',{'a':1})==fingerprint('{"a":1}',{'a':1})
 assert fingerprint('{"a":1}',{'a':1})!=fingerprint('{ "a": 1 }',{'a':1})
def test_scale_accepts_padding_but_rejects_nonzero_excess_precision():
 assert scale('-1.2','value')==-1200000
 assert scale('0.1000000','value')==100000
 with pytest.raises(ValueError):scale('0.1000001','value')
def test_scale_cache_keeps_exact_values():
 assert _scale_text("0.500000")==500000
 assert _scale_text("0.500000")==500000
def test_worker_indices_are_unique_and_bounded():
 assert parse_worker_indices("0,3,7",8)==[0,3,7]
 with pytest.raises(ValueError):parse_worker_indices("0,0",8)
 with pytest.raises(ValueError):parse_worker_indices("8",8)

def test_completion_checks_size_on_the_existing_blob():
 class Blob:
  def __init__(self,record):self.record,self.size=record,None
  def exists(self):return self.record is not None
  def reload(self):
   from google.api_core.exceptions import NotFound
   if self.record is None:raise NotFound("missing")
   self.size=self.record["size"]
  def download_as_text(self):return self.record["text"]
 class Bucket:
  def __init__(self,records):self.records=records
  def blob(self,name):return Blob(self.records.get(name))
 source=Source("gs://raw/raw/2026-08-16/0900.jsonl.zst",123,"2026-08-16","0900","regular_hour")
 import json
 from dataclasses import asdict
 from cloud_convert import cname,key
 source_id=key(source.uri)
 files=[{"name":"output.parquet","bytes":42}]
 manifest=json.dumps({"version":1,"source":asdict(source),"files":files})
 bucket=Bucket({cname("run",source_id):{"size":len(manifest),"text":manifest},"output.parquet":{"size":42}})
 assert complete(bucket,"run",source,source_id)
 bucket.records["output.parquet"]["size"]=41
 assert not complete(bucket,"run",source,source_id)
 del bucket.records["output.parquet"]
 assert not complete(bucket,"run",source,source_id)
