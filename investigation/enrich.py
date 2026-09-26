"""Retrospective category coverage diagnostics; never used by causal policy probes.

Next-day indices identify newly listed intraday assets absent from midnight lists.
Their labels are explicitly future metadata for the sampled hour.
"""
import json,sys
from collections import Counter
from datetime import date,timedelta
from probe import RESULTS,CACHE,download,save
from analyze import category,classify_index

def enrich(i):
    s=json.loads((RESULTS/'plan.json').read_text())['samples'][i]
    day=date.fromisoformat(s['path'].split('/')[1]);nextday=day+timedelta(days=1)
    source=f'raw/_index/{nextday}/polymarket_index.json'
    p=download(source)
    x,ir=classify_index(p);mi=x['market_index']
    rows=json.loads((RESULTS/f'markets_{i:02d}.json').read_text());matched=0
    for r in rows:
        old=r['category'];r['same_day_index_category']=old
        found=[mi[a] for a in r['asset_ids'] if a in mi]
        if found:
            matched+=1;v=found[0]
            r['descriptive_category']=category(' '.join((v.get(k,'') or '') for k in ['question','event_title']))
            r['descriptive_title']=v.get('question');r['descriptive_start']=v.get('start_time');r['descriptive_end']=v.get('end_time')
        else:r['descriptive_category']=old
    save(RESULTS/f'enriched_{i:02d}.json',rows)
    save(RESULTS/f'enrichment_{i:02d}.json',{'source':source,'generated_at':x.get('generated_at'),'next_day_matches':matched,'markets':len(rows),
                                          'categories':Counter(r['descriptive_category'] for r in rows)})
    print(i,'nextday matches',matched,'of',len(rows),flush=True)

if __name__=='__main__':enrich(int(sys.argv[1]))
