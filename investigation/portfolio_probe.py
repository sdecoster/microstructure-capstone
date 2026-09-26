"""Bounded real-feed diagnostics and exact compact portfolio byte measurements.

Ten seconds of receive-time history selects sports; only later rows are costed.
Current API metadata supplies identities only, never liquidity/ranking inputs.
"""
import io,json,sys,time,hashlib,re,statistics
from collections import Counter,defaultdict
from datetime import datetime
import zstandard as zstd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from probe import ROOT,CACHE,RESULTS,manifest,save
from continuity_catalog import family,stamp,load

SPORTS={'MLB','WNBA','ATP tennis','WTA tennis','Counter-Strike','League of Legends','Dota 2'}
COINS=['BTC','ETH','SOL','XRP']
def scaled(value):
    if value is None:return None
    s=str(value);a,_,b=s.partition('.')
    if len(b)>6:
        if b[6:].strip('0'):raise ValueError('Precision exceeds six decimals')
        b=b[:6]
    n=int(a)*1000000+(-1 if s.startswith('-') else 1)*int(b.ljust(6,'0') or 0)
    if abs(n)>=2**63:raise OverflowError('Scaled source number exceeds int64')
    return n
def reader(path,fraction=0):
    begun=time.perf_counter()
    with path.open('rb') as raw,zstd.ZstdDecompressor().stream_reader(raw) as decoded:
        if fraction:
            target=int(path.stat().st_size*fraction)
            while raw.tell()<target:
                if time.perf_counter()-begun>35:raise TimeoutError('Interior skip exceeded 35s')
                if not decoded.read(1024**2):return
        with io.TextIOWrapper(decoded,encoding='utf-8') as lines:
            if fraction:lines.readline()
            for seq,line in enumerate(lines,1):
                if seq>900000 or time.perf_counter()-begun>30:break
                if not line.endswith('\n'):break
                yield seq,json.loads(line),raw.tell(),len(line.encode('utf-8'))
def q(v):
    v=sorted(v)
    return {'n':len(v),'min':v[0],'median':statistics.median(v),'p95':v[int((len(v)-1)*.95)],'max':v[-1]} if v else {'n':0}
def run(i):
    start=time.perf_counter();spec=load(RESULTS/'plan.json')['samples'][i]
    path=ROOT/spec['local'] if 'local' in spec else CACHE/(spec['path']+'.prefix-67108864')
    metadata={r['market']:r['metadata'] for r in load(RESULTS/f'family_markets_{i:02d}.json') if r['metadata']}
    identities=RESULTS/'identities.json'
    if identities.exists():metadata.update(load(identities))
    assetmeta={a:r['metadata'] for r in load(RESULTS/f'family_markets_{i:02d}.json') for a in r['asset_ids'] if r['metadata']}
    seen=set();kinds=Counter();schemas=Counter();lag=[];dups=0;outerbytes=0;outercount=0;feedbytes=0;post_records=0
    warm=defaultdict(lambda:{'updates':0,'notional':0.,'spreads':[]});akey={};owners={};counts=defaultdict(Counter)
    data={'price_changes':[],'trades':[],'book_levels':[],'snapshots':[]};lo=None;hi=None;firstpos=None;cutpos=None;lastpos=None
    for seq,o,pos,nbytes in reader(path,spec.get('start_fraction',0)):
        outercount+=1;outerbytes+=nbytes;lastpos=pos
        recv=int(datetime.fromisoformat(o['timestamp'].replace('Z','+00:00')).timestamp()*1000)
        if lo is None:lo=recv;firstpos=pos
        hi=recv;early=recv<=lo+10000
        if not early:post_records+=1
        if not early and cutpos is None:cutpos=pos
        c=o.get('content');typ=o.get('message_type');kinds[typ]+=1
        if isinstance(c,str):
            try:c=json.loads(c)
            except ValueError:continue
        if not isinstance(c,dict):continue
        if typ=='market_metadata' and isinstance(c.get('market'),dict):
            v={**c['market'],'event_slug':c.get('event_slug'),'event_title':c.get('event_title')}
            if v.get('conditionId'):metadata[v['conditionId']]=v
        if typ!='feed_message':continue
        feedbytes+=nbytes
        event=c.get('event_type');schemas[(event,tuple(sorted(c)))]+=1
        mid=c.get('market')
        if not isinstance(mid,str):continue
        ts=int(c.get('timestamp') or recv)
        if seq%20==0:lag.append((recv-ts)/1000)
        fingerprint=hashlib.blake2b(json.dumps(c,sort_keys=True,separators=(',',':')).encode(),digest_size=16).digest()
        if fingerprint in seen:dups+=1;continue
        seen.add(fingerprint)
        changes=c.get('price_changes',[]) if event=='price_change' else [c]
        for ch in changes:
            asset=ch.get('asset_id')
            if not asset:continue
            asset=str(asset);key=akey.setdefault(asset,len(akey));owners[key]=mid
            if mid not in metadata and asset in assetmeta:metadata[mid]=assetmeta[asset]
            if event=='price_change':
                counts[mid]['updates']+=1
                if early:
                    warm[mid]['updates']+=1
                    b,a=ch.get('best_bid'),ch.get('best_ask')
                    if b is not None and a is not None and 0<float(b)<float(a)<1:warm[mid]['spreads'].append(float(a)-float(b))
                else:
                    if ch['side'] not in ['BUY','SELL']:raise ValueError('Unknown side')
                    data['price_changes'].append((key,ts,recv,seq,ch['side']=='BUY',scaled(ch['price']),scaled(ch['size']),scaled(ch.get('best_bid')),scaled(ch.get('best_ask'))))
            elif event=='last_trade_price':
                counts[mid]['trades']+=1
                if early:warm[mid]['notional']+=float(c['price'])*float(c['size'])
                else:data['trades'].append((key,ts,recv,seq,c.get('side')=='BUY',scaled(c['price']),scaled(c['size']),scaled(c.get('fee_rate_bps')),bytes.fromhex(c['transaction_hash'].removeprefix('0x')) if c.get('transaction_hash') else None))
            elif event=='book':
                counts[mid]['snapshots']+=1
                if not early:
                    data['snapshots'].append((key,ts,recv,seq,bytes.fromhex(c['hash'].removeprefix('0x')) if c.get('hash') else None))
                    for side,lev in [(True,c.get('bids',[])),(False,c.get('asks',[]))]:
                        for level in lev:data['book_levels'].append((key,seq,side,scaled(level['price']),scaled(level['size'])))
        if sum(len(v) for v in data.values())>=350000:break
    if cutpos is None or lastpos<=cutpos:raise RuntimeError('Not enough post-warmup data')
    # Classification is structural identity, not current API activity. Unknowns are reported.
    fam={m:family(metadata[m]) if m in metadata else 'Unmapped' for m in counts}
    sport=[]
    for m,w in warm.items():
        title=metadata.get(m,{}).get('question') or ''
        if fam.get(m) not in SPORTS or not re.search(r'\bvs\.?\s',title,re.I):continue
        if re.search(r'spread|total|over/under|\bmap \d|\bgame \d|\bset \d',title,re.I):continue
        if w['updates']<2 or not w['spreads'] or statistics.median(w['spreads'])>.0500001:continue
        sport.append(m)
    sport.sort(key=lambda m:(-warm[m]['notional'],-warm[m]['updates'],m))
    def crypto(horizons,coins=COINS):return {m for m,f in fam.items() if f in {c+' '+h for c in coins for h in horizons}}
    c4=crypto(['5m']);c8=crypto(['5m','15m']);c12=crypto(['5m','15m','1h']);c15=c12|crypto(['5m'],['BNB','DOGE','HYPE'])
    portfolios={'all':set(counts),'crypto4':c4,'crypto8':c8,'crypto12':c12,'crypto15':c15,
                'crypto15m4':crypto(['15m']),'crypto1h4':crypto(['1h']),'crypto15m1h8':crypto(['15m','1h']),
                'crypto_slow12':crypto(['15m','1h','4h']),'crypto_all16':crypto(['5m','15m','1h','4h']),
                'sports5':set(sport[:5]),'sports15':set(sport[:15]),'mixed8plus7':c8|set(sport[:7]),'mixed12plus3':c12|set(sport[:3])}
    defs={'price_changes':[('asset',pa.uint32()),('time',pa.int64()),('receive',pa.int64()),('seq',pa.uint32()),('buy',pa.bool_()),('price',pa.int64()),('size',pa.int64()),('bid',pa.int64()),('ask',pa.int64())],
          'trades':[('asset',pa.uint32()),('time',pa.int64()),('receive',pa.int64()),('seq',pa.uint32()),('buy',pa.bool_()),('price',pa.int64()),('size',pa.int64()),('fee',pa.int64()),('tx',pa.binary())],
          'snapshots':[('asset',pa.uint32()),('time',pa.int64()),('receive',pa.int64()),('seq',pa.uint32()),('hash',pa.binary())],
          'book_levels':[('asset',pa.uint32()),('seq',pa.uint32()),('buy',pa.bool_()),('price',pa.int64()),('size',pa.int64())]}
    tables={name:pa.table({col:pa.array([r[j] for r in rr],type=kind) for j,(col,kind) in enumerate(defs[name])}) for name,rr in data.items()}
    def encoded(tab):
        if not tab.num_rows:return 0
        sink=pa.BufferOutputStream();pq.write_table(tab,sink,compression='zstd',compression_level=3,use_dictionary=True)
        size=sink.tell()
        if not pq.read_table(pa.BufferReader(sink.getvalue())).equals(tab):raise AssertionError('Real-data Parquet round-trip mismatch')
        return size
    estimates={};encoded_families={}
    for name,mids in {**portfolios,**{'family:'+f:{m for m in fam if fam[m]==f} for f in set(fam.values()) if f!='Unmapped'}}.items():
        keys=[k for k,m in owners.items() if m in mids];allowed=pa.array(keys,type=pa.uint32());sizes={};nrows=0
        for tabname,tab in tables.items():
            sub=tab.filter(pc.is_in(tab['asset'],value_set=allowed));sizes[tabname]=encoded(sub);nrows+=sub.num_rows
        keyset=set(keys)
        aids=[a for a,k in akey.items() if k in keyset]
        dims=pa.table({'asset':pa.array([akey[a] for a in aids],type=pa.uint32()),'token':pa.array([int(a).to_bytes(32,'big') for a in aids],type=pa.binary(32)),
                       'condition':pa.array([bytes.fromhex(owners[akey[a]][2:]) for a in aids],type=pa.binary(32))})
        sizes['dimensions']=encoded(dims)
        item={'bytes':sum(sizes.values()),'by_table':sizes,'rows':nrows,'markets':len(mids)}
        if name.startswith('family:'):encoded_families[name[7:]]=item
        else:estimates[name]=item
    info=zstd.get_frame_parameters(path.open('rb').read(18))
    result={'sample':i,'source':spec['path'],'outer_records':outercount,'duplicates':dups,'outer_json_bytes':outerbytes,
            'span_seconds':(hi-lo)/1000,'post_seconds':(hi-lo-10000)/1000,'post_compressed_bytes_approx':lastpos-cutpos,
            'first_receive_ms':lo,'last_receive_ms':hi,'kinds':kinds,'schemas':[{'type':k[0],'keys':k[1],'count':v} for k,v in schemas.items()],
            'feed_json_bytes':feedbytes,'post_outer_records':post_records,'numeric_scale':1000000,
            'lag_seconds':q(lag),'frame':{'window_size':info.window_size,'checksum':info.has_checksum,'dictionary_id':info.dict_id},
            'portfolios':estimates,'family_bytes':encoded_families,'sports_eligible':len(sport),
            'sports_rank':[{ 'market':m,'family':fam[m],'title':metadata.get(m,{}).get('question'),'warmup_trade_notional':warm[m]['notional'],'warmup_updates':warm[m]['updates']} for m in sport[:15]],
            'families':{f:{'markets':sum(v==f for v in fam.values()),'updates':sum(c['updates'] for m,c in counts.items() if fam[m]==f),'trades':sum(c['trades'] for m,c in counts.items() if fam[m]==f)} for f in set(fam.values())},
            'unknown_updates':sum(c['updates'] for m,c in counts.items() if fam[m]=='Unmapped'),
            'total_updates':sum(c['updates'] for c in counts.values()),'round_trip_verified':True,'seconds':time.perf_counter()-start}
    result['identity_coverage_update_pct']=100*(1-result['unknown_updates']/result['total_updates'])
    result['unmapped_leaders']=[{'market':m,**c} for m,c in sorted(counts.items(),key=lambda x:-x[1]['updates']) if fam[m]=='Unmapped'][:30]
    save(RESULTS/f'portfolio_{i:02d}.json',result)
    print(json.dumps({k:result[k] for k in ['sample','outer_records','span_seconds','post_compressed_bytes_approx','sports_eligible','unknown_updates','total_updates','seconds']}))
if __name__=='__main__':run(int(sys.argv[1]))
