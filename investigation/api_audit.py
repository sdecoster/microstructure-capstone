"""Bounded random audit of market metadata, including unresolved index joins.
Current tags are descriptive only. At most 12 condition IDs per API request.
"""
import json,random
from collections import Counter
from api_metadata import fetch
from probe import RESULTS,save

if __name__=='__main__':
    report=[]
    for sample in [0,3,5,6,7,8,9,10,11]:
        rows=json.loads((RESULTS/f'enriched_{sample:02d}.json').read_text())
        candidates=[r for r in rows if r['descriptive_category']=='Unmapped']
        if sample==0:candidates=[r for r in rows if r['descriptive_category'] in ['Mentions','Unclassified']]
        chosen=random.Random(20260925+sample).sample(candidates,min(12,len(candidates)))
        mids=[r['market'] for r in chosen];found={}
        for closed in ['false','true']:
            r=fetch(f'audit_{sample}_{closed}','https://gamma-api.polymarket.com/markets',
                    [('condition_ids',m) for m in mids]+[('closed',closed),('limit',len(mids)),('include_tag','true')])
            for m in r.get('data',[]) if isinstance(r.get('data'),list) else []:
                if m.get('conditionId') not in mids:raise RuntimeError('API ignored requested condition filter')
                found[m['conditionId']]=m
        cat=Counter();details=[]
        for mid,m in found.items():
            tags={t.get('slug') for t in m.get('tags',[]) or []}
            # Preserve all tags; broad display category only, priority fixed.
            category=next((x for x in ['sports','crypto','weather','politics','mentions'] if x in tags),'other')
            cat[category]+=1
            details.append({'market':mid,'question':m.get('question'),'createdAt':m.get('createdAt'),
                            'startDate':m.get('startDate'),'endDate':m.get('endDate'),
                            'tags':sorted(t for t in tags if t),'token_ids':m.get('clobTokenIds'),'outcomes':m.get('outcomes')})
        report.append({'sample':sample,'requested':len(mids),'matched':len(found),'categories':cat,'details':details})
    save(RESULTS/'api_audit.json',report)
