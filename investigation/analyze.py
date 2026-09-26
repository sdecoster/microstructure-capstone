"""Analyze one bounded, real compressed prefix; never infer full-hour market coverage.

Outputs JSON statistics and per-market observations, not expanded raw data.
"""
import argparse, hashlib, json, math, re, statistics, time
from collections import Counter, defaultdict
from decimal import Decimal
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from probe import CACHE, RESULTS, ROOT, download, records, save

def category(title):
    t=title.lower()
    if re.search(r'\b(mention|mentions|say|says|said)\b',t):return 'Mentions'
    if re.search(r'\b(bitcoin|btc|ethereum|eth|solana|xrp|bnb|dogecoin|hyperliquid|hype|zcash|crypto)\b|up or down',t):return 'Crypto'
    if re.search(r'temperature|weather|rainfall|hurricane',t):return 'Weather'
    if re.search(r'\bvs\b|\b(nba|nfl|mlb|nhl|fifa|premier league|champions league|world cup|stanley cup|super bowl)\b',t):return 'Sports/esports'
    if re.search(r'\b(trump|election|president|democrat|republican|senate|congress|minister|governor)\b',t):return 'Politics'
    if re.search(r'\b(fed|inflation|gdp|stock|nasdaq|s&p|gold|oil)\b',t):return 'Economics/finance'
    return 'Unclassified'

def classify_index(path):
    x=json.loads(path.read_text(encoding='utf-8'))
    mi=x.get('market_index',{})
    if not isinstance(mi,dict):raise ValueError('Unexpected index schema')
    market={str(v.get('market_id',k)):v for k,v in mi.items()}
    rows=[]
    for mid,v in market.items():
        title=(v.get('event_title','') or '')+' '+(v.get('question','') or '')
        rows.append({'market_id':mid,'category':category(title),'title':title,
                     'start':v.get('start_time'),'end':v.get('end_time')})
    return x,rows

def run(sample):
    spec=json.loads((RESULTS/'plan.json').read_text())['samples'][sample]
    path=ROOT/spec['local'] if 'local' in spec else download(spec['path'],8*1024**2)
    ip=CACHE/spec['index']
    if not ip.exists() and 'local' in spec:ip=ROOT/'data/exploration_sample'/spec['index']
    index,ir=classify_index(ip) if ip.exists() else ({},[])
    start=time.perf_counter(); seen=set(); count=Counter(); duplicates=0; assets={}; market_assets=defaultdict(set)
    pc=[]; trades=[]; books=[]; snaps=[]; event_stats=[]; raw_compressor=__import__('zstandard').ZstdCompressor(level=3).compressobj()
    recompressed=0; uncompressed=0; recv_times=[]; event_times=[]; prev=None; reversals=0; schema=Counter(); scales=Counter()
    for seq,outer in records(path,max_lines=100_000,deadline=35,start_fraction=spec.get('start_fraction',0)):
        wire=(json.dumps(outer,separators=(',',':'))+'\n').encode();uncompressed+=len(wire)
        recompressed+=len(raw_compressor.compress(wire))
        c=outer.get('content',{})
        if isinstance(c,str):
            try:c=json.loads(c)
            except ValueError:c={}
        if not isinstance(c,dict):schema['non_dict_content']+=1;continue
        typ=c.get('event_type',outer.get('message_type','unknown'));schema[typ]+=1
        try:recv=int(pd.Timestamp(outer['timestamp']).value//1_000_000)
        except Exception:continue
        recv_times.append(recv)
        try:ts=int(c.get('timestamp'))
        except (TypeError,ValueError):ts=recv
        event_times.append(ts)
        if prev is not None and ts<prev:reversals+=1
        prev=ts
        fp=hashlib.blake2b(json.dumps(c,sort_keys=True,separators=(',',':')).encode(),digest_size=16).digest()
        if fp in seen:duplicates+=1;continue
        seen.add(fp);count[typ]+=1
        m=c.get('market')
        if not isinstance(m,str):continue
        base={'market':m,'time':ts,'receive_ms':recv,'seq':seq}
        update_count=0; levels=0; tight=[]; depths=[]
        if typ=='price_change':
            for ch in c.get('price_changes',[]):
                aid=str(ch['asset_id']);assets[aid]=m;market_assets[m].add(aid)
                pc.append({**base,'asset':aid,**{k:ch.get(k) for k in ['price','size','side','best_bid','best_ask']}})
                scales['price_scale_'+str(max(0,-Decimal(str(ch['price'])).as_tuple().exponent))]+=1
                update_count+=1
                try:
                    b,a=float(ch['best_bid']),float(ch['best_ask'])
                    if 0<b<a<1:tight.append(a-b)
                except (ValueError,KeyError,TypeError):pass
        elif typ=='last_trade_price':
            aid=str(c['asset_id']);assets[aid]=m;market_assets[m].add(aid)
            trades.append({**base,'asset':aid,**{k:c.get(k) for k in ['price','size','side','fee_rate_bps','transaction_hash']}})
        elif typ=='book':
            aid=str(c['asset_id']);assets[aid]=m;market_assets[m].add(aid)
            snaps.append({**base,'asset':aid,'hash':c.get('hash')})
            bid=c.get('bids',[]);ask=c.get('asks',[])
            if bid and ask:
                b=max(float(v['price']) for v in bid);a=min(float(v['price']) for v in ask)
                if 0<b<a<1:
                    tight.append(a-b)
                    # Share depth within one cent, minimum of buy/sell sides.
                    depths.append(min(sum(float(v['size']) for v in bid if float(v['price'])>=b-.01000001),
                                      sum(float(v['size']) for v in ask if float(v['price'])<=a+.01000001)))
            for side,lev in [('BUY',bid),('SELL',ask)]:
                for v in lev:
                    books.append({'seq':seq,'asset':aid,'side':side,'price':v['price'],'size':v['size']});levels+=1
        event_stats.append({'market':m,'recv':recv,'updates':update_count,'trade':int(typ=='last_trade_price'),
                            'book':int(typ=='book'),'levels':levels,'spreads':tight,'depth':depths})
    recompressed+=len(raw_compressor.flush())
    if not recv_times:raise RuntimeError('No usable records')
    lo,hi=min(recv_times),max(recv_times)
    # Fixed elapsed-receive-time decision, never a cutoff inferred from future activity.
    # Prefixes are exceptionally short; interiors allow a longer observation window.
    decision_seconds=20 if 'local' in spec else 1
    cut=lo+decision_seconds*1000
    summary={}
    for e in event_stats:
        m=e['market'];s=summary.setdefault(m,{'market':m,'messages':0,'updates':0,'trades':0,'books':0,'book_levels':0,'spreads':[],'depth':[],
                                             'early_updates':0,'early_spreads':[],'early_trades':0,'early_messages':0,'late_rows':0})
        s['messages']+=1;s['updates']+=e['updates'];s['trades']+=e['trade'];s['books']+=e['book'];s['book_levels']+=e['levels']
        s['spreads']+=e['spreads'];s['depth']+=e['depth']
        if e['recv']<=cut:
            s['early_messages']+=1
            s['early_updates']+=e['updates'];s['early_spreads']+=e['spreads'];s['early_trades']+=e['trade']
        else:s['late_rows']+=e['updates']+e['trade']+e['levels']
    mi=index.get('market_index',{});cat_counts=Counter();matched=0
    for m,s in summary.items():
        # Index dictionary keys are asset/token IDs, NOT condition IDs converted to decimal.
        matches=[mi[a] for a in market_assets[m] if a in mi]
        if matches:matched+=1
        s['category']=category(' '.join((matches[0].get(k,'') or '') for k in ['question','event_title'])) if matches else 'Unmapped'
        s['title']=matches[0].get('question') if matches else None
        s['token_count']=len(market_assets[m]);s['asset_ids']=sorted(market_assets[m]);cat_counts[s['category']]+=1
        for f in ['spreads','depth','early_spreads']:
            s['median_'+f]=statistics.median(s[f]) if s[f] else None
            s[f+'_observations']=len(s[f]);del s[f]
    # Lossless compact benchmark, all maps INCLUDED, exact dynamic Decimal scales.
    key={a:i for i,a in enumerate(sorted(assets))};mkey={m:i for i,m in enumerate(sorted(set(assets.values())))}
    def encode(rows,table):
        if not rows:return pa.table({})
        columns={k:[r.get(k) for r in rows] for k in rows[0]}
        arr={}
        for k,v in columns.items():
            if k=='market':continue  # asset -> market dimension supplies it
            if k=='asset':arr[k]=pa.array([key[x] for x in v],type=pa.uint32())
            elif k in ['time','receive_ms']:arr[k]=pa.array(v,type=pa.int64())
            elif k=='seq':arr[k]=pa.array(v,type=pa.uint32())
            elif k=='side':
                if any(x not in ['BUY','SELL'] for x in v):raise ValueError('Unknown side; do not silently coerce')
                arr[k]=pa.array([x=='BUY' for x in v],type=pa.bool_())
            elif k in ['price','size','best_bid','best_ask','fee_rate_bps']:
                ds=[Decimal(str(x)) if x is not None else None for x in v]
                scale=max((max(0,-x.as_tuple().exponent) for x in ds if x is not None),default=0)
                arr[k]=pa.array(ds,type=pa.decimal128(30,scale))
            elif k in ['hash','transaction_hash']:
                arr[k]=pa.array([bytes.fromhex(x.removeprefix('0x')) if x else None for x in v],type=pa.binary())
            else:arr[k]=pa.array(v)
        return pa.table(arr)
    tables={k:encode(v,k) for k,v in [('price_changes',pc),('trades',trades),('book_levels',books),('snapshots',snaps)]}
    tables['assets']=pa.table({'asset':pa.array(list(key.values()),type=pa.uint32()),'market':pa.array([mkey[assets[a]] for a in key],type=pa.uint32()),
                              'token_id':pa.array([int(a).to_bytes(32,'big') for a in key],type=pa.binary(32))})
    tables['markets']=pa.table({'market':pa.array(list(mkey.values()),type=pa.uint32()),'condition':pa.array([bytes.fromhex(m[2:]) for m in mkey],type=pa.binary(32))})
    sizes={};compression_seconds={};round_trip_seconds={}
    for level in [3,9]:
        part={};write_seconds=0;read_seconds=0
        for name,tab in tables.items():
            if not tab.num_rows:part[name]=0;continue
            a=time.perf_counter()
            sink=pa.BufferOutputStream();pq.write_table(tab,sink,compression='zstd',compression_level=level,use_dictionary=True)
            part[name]=sink.tell();write_seconds+=time.perf_counter()-a
            a=time.perf_counter();restored=pq.read_table(pa.BufferReader(sink.getvalue()))
            if not restored.equals(tab):raise AssertionError(f'{name} Zstd {level} failed exact round-trip')
            read_seconds+=time.perf_counter()-a
        sizes[str(level)]=part;compression_seconds[str(level)]=write_seconds;round_trip_seconds[str(level)]=read_seconds
    # These are short-window causal sensitivity probes, NOT estimated production eligibility.
    policy=[];total_late=sum(s['late_rows'] for s in summary.values());early=sorted([s for s in summary.values() if s['early_messages']],key=lambda s:(-s['early_updates'],s['market']))
    for name,chosen in [
        ('all',set(summary)),
        ('early_2_updates', {s['market'] for s in early if s['early_updates']>=2}),
        ('early_10_updates', {s['market'] for s in early if s['early_updates']>=10}),
        ('early_50_updates', {s['market'] for s in early if s['early_updates']>=50}),
        ('early_10_and_spread_le_5c',{s['market'] for s in early if s['early_updates']>=10 and s['median_early_spreads'] is not None and s['median_early_spreads']<=.0500001}),
        ('top_10pct_early_activity',{s['market'] for s in early[:max(1,math.ceil(len(early)*.1))]}),
        ('stable_hash_10pct',{s['market'] for s in early if int(hashlib.sha256(('20260925'+s['market']).encode()).hexdigest()[:8],16)/2**32 <.1})]:
        policy.append({'policy':name,'selected':len(chosen),'markets':len(summary),'late_rows':sum(s['late_rows'] for m,s in summary.items() if m in chosen),
                       'all_late_rows':total_late})
    out={'path':spec['path'],'sample':sample,'outer_messages':len(recv_times),'schema':schema,'unique_events':count,
         'duplicates':duplicates,'span_seconds':(hi-lo)/1000,'decision_seconds':decision_seconds,
         'receive_start_ms':lo,'receive_end_ms':hi,'event_reversals':reversals,
         'markets':len(summary),'assets':len(assets),'assets_per_market':Counter(map(len,market_assets.values())),
         'matched_index_markets':matched,'categories':cat_counts,'scales':scales,'rows':{k:len(v) for k,v in [('price_changes',pc),('trades',trades),('book_levels',books),('snapshots',snaps)]},
         'recompressed_complete_json_bytes':recompressed,'complete_json_bytes':uncompressed,'parquet_bytes':sizes,'compression_seconds':compression_seconds,
         'scan_and_benchmark_seconds':time.perf_counter()-start,'policies':policy,
         'parquet_round_trip_verified':True,'round_trip_seconds':round_trip_seconds,
         'index':{'generated_at':index.get('generated_at'),'tokens':len(mi),'distinct_markets':len(ir),'categories':Counter(r['category'] for r in ir)}}
    save(RESULTS/f'sample_{sample:02d}.json',out)
    save(RESULTS/f'markets_{sample:02d}.json',list(summary.values()))
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('sample',type=int);run(p.parse_args().sample)
