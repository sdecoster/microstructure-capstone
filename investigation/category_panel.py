"""Uniform market draws within each observed window, not an archive-wide census.

Current official metadata is retrospective/descriptive and never a filter input.
Each request is at most 16 markets, capped by api_metadata.fetch at 2 MiB.
"""
import json,random
from api_metadata import fetch
from probe import RESULTS,save

def broad(tags):
    # Store every tag as well; exclusive display buckets are a declared convenience.
    for label,slugs in [
        ('Mentions',{'mentions','mention-markets'}),
        ('Sports/esports',{'sports','esports'}),('Crypto',{'crypto'}),
        ('Weather',{'weather'}),('Politics',{'politics','elections'}),
        ('Economics/finance',{'economy','economics','finance','business'})]:
        if tags & slugs:return label
    return 'Other'

def run(i):
    rows=json.loads((RESULTS/f'markets_{i:02d}.json').read_text())
    chosen=random.Random(50000+i).sample(sorted(rows,key=lambda r:r['market']), min(16,len(rows)))
    ids=[r['market'] for r in chosen];found={}
    for closed in ['false','true']:
        r=fetch(f'panel_{i}_{closed}','https://gamma-api.polymarket.com/markets',
                [('condition_ids',m) for m in ids]+[('closed',closed),('limit',len(ids)),('include_tag','true')])
        if r.get('status')!=200 or not isinstance(r.get('data'),list):
            raise RuntimeError(f'Panel {i}: failed metadata request')
        for m in r['data']:
            if m.get('conditionId') not in ids:raise RuntimeError('Condition filter not honored')
            found[m['conditionId']]=m
    out=[]
    for row in chosen:
        m=found.get(row['market'],{});tags={t['slug'] for t in m.get('tags',[]) if t.get('slug')}
        out.append({'sample':i,'market':row['market'],'category':broad(tags) if m else 'Unmatched',
                    'tags':sorted(tags),'title':m.get('question'),'updates':row['updates'],
                    'start':m.get('startDate'),'end':m.get('endDate'),'event_start':m.get('eventStartTime'),
                    'created':m.get('createdAt'),'token_ids':m.get('clobTokenIds'),'outcomes':m.get('outcomes')})
    save(RESULTS/f'category_panel_{i:02d}.json',out)

if __name__=='__main__':
    import sys
    run(int(sys.argv[1]))
