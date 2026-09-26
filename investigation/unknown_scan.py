"""Bounded identity audit beyond the initial 100k records; no liquidity backfill."""
import json,sys
from collections import Counter
from probe import CACHE,RESULTS,ROOT,save
from continuity_catalog import load
from portfolio_probe import reader
from api_metadata import fetch
from identity_cache import identities
def run(i):
    spec=load(RESULTS/'plan.json')['samples'][i]
    path=ROOT/spec['local'] if 'local' in spec else CACHE/(spec['path']+'.prefix-67108864')
    known=set(identities())
    known.update(r['market'] for r in load(RESULTS/f'family_markets_{i:02d}.json') if r['metadata'])
    counts=Counter();old=RESULTS/f'portfolio_{i:02d}.json';cap=max(400000,load(old)['outer_records'] if old.exists() else 0)
    for seq,o,_,_ in reader(path,spec.get('start_fraction',0)):
        if seq>cap:break
        if o.get('message_type')!='feed_message':continue
        c=o.get('content')
        if isinstance(c,str):
            try:c=json.loads(c)
            except ValueError:continue
        if isinstance(c,dict) and isinstance(c.get('market'),str) and c['market'] not in known:counts[c['market']]+=1
    ids=[m for m,n in counts.most_common(60)]
    save(RESULTS/f'unknown_scan_{i:02d}.json',{'sample':i,'unknown_leaders':counts.most_common(60)})
    for batch in range(0,len(ids),30):
        mids=ids[batch:batch+30]
        for closed in ['false','true']:
            r=fetch(f'extended_id_{i}_{batch}_{closed}','https://gamma-api.polymarket.com/markets',
                    [('condition_ids',m) for m in mids]+[('closed',closed),('limit',len(mids)),('include_tag','true')])
            for m in r.get('data',[]) if isinstance(r.get('data'),list) else []:
                if m.get('conditionId') not in mids:raise ValueError('Unrequested market')
    print(i,'looked up',len(ids),'identities')
if __name__=='__main__':run(int(sys.argv[1]))
