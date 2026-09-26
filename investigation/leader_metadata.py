"""Identity-only official metadata; never use current liquidity to rank history."""
import json,sys
from probe import RESULTS
from api_metadata import fetch
def run(i):
    spec=json.loads((RESULTS/'continuity_catalog.json').read_text())['candidate_api'][i]
    mids=spec['markets'];found=set()
    for closed in ['false','true']:
        r=fetch(f'leaders_{i}_{closed}','https://gamma-api.polymarket.com/markets',
            [('condition_ids',m) for m in mids]+[('closed',closed),('limit',len(mids)),('include_tag','true')])
        for m in r.get('data',[]) if isinstance(r.get('data'),list) else []:
            if m.get('conditionId') not in mids:raise ValueError('Unrequested condition returned')
            found.add(m['conditionId'])
    print(i,'matched',len(found),'of',len(mids))
if __name__=='__main__':run(int(sys.argv[1]))
