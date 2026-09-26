"""Offline, source-byte-weighted cost extrapolations; not full-archive measurements."""
import json,re,statistics
from collections import Counter,defaultdict
from probe import RESULTS,CACHE,manifest,save
from continuity_catalog import load
def q(v):
    v=sorted(v)
    return {'n':len(v),'min':v[0],'median':statistics.median(v),'max':v[-1]} if v else {'n':0}
def run():
    plan=load(RESULTS/'plan.json')['samples'];samples=[load(RESULTS/f'portfolio_{i:02d}.json') for i in range(len(plan))]
    mf=manifest();raw={p:e['bytes'] for p,e in mf.items() if re.fullmatch(r'raw/\d{4}-\d{2}-\d{2}/.*\.jsonl\.zst',p)}
    names=list(samples[0]['portfolios']);estimates={}
    for name in names:
        parts=[]
        for i in range(12):
            a,b=plan[i]['stratum'];weight=sum(v for p,v in raw.items() if a<=p.split('/')[1]<=b)
            chosen=20+i if i<3 and len(samples)>=23 else i
            s=samples[chosen];n=s['portfolios'][name]['bytes'];den=s['post_compressed_bytes_approx']
            parts.append({'sample':chosen,'raw_GB':weight/1e9,'ratio':n/den,'estimated_GB':weight*n/den/1e9})
        early=sum(p['estimated_GB'] for p in parts[:3]);later=sum(p['estimated_GB'] for p in parts[3:]);total=early+later
        estimates[name]={'archive_GB':total,'early_GB':early,'later_GB':later,'strata':parts,
                         'post_period_observed_hour_MB':q([s['portfolios'][name]['bytes']/s['post_compressed_bytes_approx']*mf[s['source']]['bytes']/1e6 for s in samples if s['sample'] in list(range(3,16))+[17,18,19]]),
                         'selected_markets':q([s['portfolios'][name]['markets'] for s in samples])}
    era={}
    for label,ix in [('early',[0,1,2,16]),('later',list(range(3,12))+[17,18,19]),('interiors',list(range(12,16)))]:
        ss=[samples[i] for i in ix]
        era[label]={'samples':ix,'duplicate_pct':q([100*s['duplicates']/s['outer_records'] for s in ss]),
                    'feed_json_bytes_per_record':q([s['feed_json_bytes']/s['kinds']['feed_message'] for s in ss]),
                    'lag_median_seconds':q([s['lag_seconds']['median'] for s in ss]),
                    'price_change_keys':[x['keys'] for x in ss[0]['schemas'] if x['type']=='price_change'],
                    'frames':[s['frame'] for s in ss],
                    'sports_eligible':q([s['sports_eligible'] for s in ss]),
                    'sports_positive_warmup_trades':q([sum(r['warmup_trade_notional']>0 for r in s['sports_rank']) for s in ss])}
    families={}
    for f in sorted({f for s in samples for f in s['families']}):
        active=[s for s in samples if s['families'].get(f,{}).get('updates',0)]
        families[f]={'windows_with_updates':len(active),'windows_with_trades':sum(s['families'].get(f,{}).get('trades',0)>0 for s in samples),
                     'sample_ids':[s['sample'] for s in active],
                     'trades':sum(s['families'].get(f,{}).get('trades',0) for s in samples),
                     'updates':sum(s['families'].get(f,{}).get('updates',0) for s in samples),
                     'token_updates_per_second':q([s['families'][f]['updates']/s['span_seconds'] for s in active])}
    result={'costs':estimates,'eras':era,'families':families,
            'sample_seconds':sum(s['span_seconds'] for s in samples),'outer_records':sum(s['outer_records'] for s in samples),
            'span_seconds':q([s['span_seconds'] for s in samples]),'runtime_seconds':q([s['seconds'] for s in samples]),
            'identity_coverage_update_pct':q([s['identity_coverage_update_pct'] for s in samples]),
            'cache_bytes':sum(p.stat().st_size for p in CACHE.rglob('*') if p.is_file()),
            'raw_GB':sum(raw.values())/1e9,'per_window':[{k:s[k] for k in ['sample','source','span_seconds','sports_eligible','sports_rank','identity_coverage_update_pct']} for s in samples]}
    save(RESULTS/'portfolio_summary.json',result)
    print('COSTS',json.dumps({k:{f:v[f] for f in ['archive_GB','early_GB','later_GB','post_period_observed_hour_MB']} for k,v in estimates.items()},indent=2))
    print('FAMILY',json.dumps({k:v for k,v in families.items() if k not in ['Other','Unmapped']},indent=2))
    print('ERA',json.dumps(era,indent=2))
    print('RESOURCES',{k:result[k] for k in ['outer_records','span_seconds','runtime_seconds','cache_bytes','identity_coverage_update_pct']})
if __name__=='__main__':run()
