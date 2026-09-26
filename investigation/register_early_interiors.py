"""Use later portions of the three existing early prefixes for cost calibration."""
from probe import RESULTS,CACHE,ROOT,save
from continuity_catalog import load
if __name__=='__main__':
    plan=load(RESULTS/'plan.json');plan['samples']=plan['samples'][:20]
    for i in range(3):
        s=dict(plan['samples'][i]);p=CACHE/(s['path']+'.prefix-134217728');assert p.exists()
        s.update(local=str(p.relative_to(ROOT)),start_fraction=.70,calibration_replacement_of=i)
        plan['samples'].append(s)
        save(RESULTS/f'family_markets_{20+i:02d}.json',load(RESULTS/f'family_markets_{i:02d}.json'))
    save(RESULTS/'plan.json',plan)
