"""Explicit sports-evening supplement; leaves original 16 choices unchanged."""
from probe import RESULTS,manifest,save
from continuity_catalog import load
if __name__=='__main__':
    p=load(RESULTS/'plan.json');base=p['samples'][:16];mf=manifest()
    for day in ['2026-05-25','2026-06-22','2026-07-11','2026-08-11']:
        path=f'raw/{day}/2300.jsonl.zst'
        assert path in mf
        base.append({'path':path,'bytes':mf[path]['bytes'],'index':f'raw/_index/{day}/polymarket_index.json',
                     'stratum':['sports_evening_supplement'],'supplement':True})
    p['samples']=base;save(RESULTS/'plan.json',p)
    print('Plan contains',len(base),'windows')
