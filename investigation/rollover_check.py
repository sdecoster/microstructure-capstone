"""Check actual current-interval crypto IDs against the bounded historical feed."""
import sys,json
from collections import Counter
from probe import RESULTS,CACHE,save
from continuity_catalog import load
from api_metadata import fetch
from portfolio_probe import reader
def run(i):
    old=load(RESULTS/f'sample_{i:02d}.json');epoch=old['receive_start_ms']//1000
    slugs=[f'{coin}-updown-{minutes}m-{epoch//(minutes*60)*(minutes*60)}' for coin in ['btc','eth','sol','xrp'] for minutes in [5,15]]
    found={}
    for closed in ['false','true']:
        r=fetch(f'roll_current_{i}_{closed}','https://gamma-api.polymarket.com/markets',
                [('slug',s) for s in slugs]+[('closed',closed),('limit',len(slugs))])
        for m in r.get('data',[]) if isinstance(r.get('data'),list) else []:
            if m.get('slug') not in slugs:raise ValueError('API ignored slug filter')
            found[m['conditionId']]={'slug':m['slug'],'question':m['question']}
    path=CACHE/(old['path']+'.prefix-67108864');hits=Counter();first={};last={};sourcefirst=None;sourcelast=None
    for seq,o,pos,n in reader(path):
        if sourcefirst is None:sourcefirst=o.get('timestamp')
        sourcelast=o.get('timestamp');c=o.get('content')
        if isinstance(c,str):
            try:c=json.loads(c)
            except ValueError:continue
        if not isinstance(c,dict) or not isinstance(c.get('market'),str):continue
        m=c['market']
        if m in found:
            hits[m]+=1;first.setdefault(m,o['timestamp']);last[m]=o['timestamp']
    result={'sample':i,'source_first':sourcefirst,'source_last':sourcelast,'records':seq,
            'contracts':[{'market':m,**v,'messages':hits[m],'first':first.get(m),'last':last.get(m)} for m,v in found.items()]}
    save(RESULTS/f'rollover_check_{i:02d}.json',result);print(json.dumps(result))
if __name__=='__main__':run(int(sys.argv[1]))
