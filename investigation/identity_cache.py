"""Compact structural identity only; deliberately exclude current volume/liquidity/status."""
from probe import CACHE,RESULTS,save
from continuity_catalog import load
def identities():
    out={}
    for p in (CACHE/'api').glob('*.json'):
        x=load(p).get('data');rows=x if isinstance(x,list) else [x] if isinstance(x,dict) else []
        for m in rows:
            if not isinstance(m,dict) or not m.get('conditionId'):continue
            ev=(m.get('events') or [{}])[0]
            out[m['conditionId']]={k:m.get(k) for k in ['conditionId','question','slug','createdAt','startDate','endDate','eventStartTime','clobTokenIds','outcomes']}
            out[m['conditionId']].update(event_slug=ev.get('slug') or m.get('slug'),event_title=ev.get('title'))
    return out
if __name__=='__main__':
    out=identities();save(RESULTS/'identities.json',out);print('Identities',len(out))
