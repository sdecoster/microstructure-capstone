"""Rebuild compact evidence tables from saved real observations; no network access."""
import json,statistics,math,hashlib,re
from collections import Counter,defaultdict
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from probe import ROOT,CACHE,RESULTS,manifest,save
from analyze import category

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def pct(a,b):return round(100*a/b,2) if b else None
def quant(v):
    v=sorted(v)
    return {'n':len(v),'min':v[0],'p25':v[int((len(v)-1)*.25)],'median':statistics.median(v),
            'p75':v[int((len(v)-1)*.75)],'max':v[-1]} if v else {'n':0}
def dt(s):
    if not s:return None
    try:return datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):return None

def main():
    samples=[read(RESULTS/f'sample_{i:02d}.json') for i in range(16)]
    rows=[read(RESULTS/f'markets_{i:02d}.json') for i in range(16)]
    union={r['market'] for rr in rows for r in rr}
    raw_assets=defaultdict(set)
    for rr in rows:
        for r in rr:raw_assets[r['market']].update(r['asset_ids'])
    needed={a for aa in raw_assets.values() for a in aa}
    labels={};index_ids={};index_stats=[]
    paths=sorted((CACHE/'raw/_index').glob('*/polymarket_index.json'))
    local=ROOT/'data/exploration_sample/raw/_index/2026-08-16/polymarket_index.json'
    if local.exists() and not any(p.parent.name=='2026-08-16' for p in paths):paths.append(local)
    for p in paths:
        x=read(p);mi=x['market_index'];uniq={str(v.get('market_id')):v for v in mi.values()}
        index_ids.update(uniq)
        token_counts=Counter(str(v.get('market_id')) for v in mi.values())
        durations=[]
        for v in uniq.values():
            a,b=dt(v.get('start_time')),dt(v.get('end_time'))
            if a and b and b>=a:durations.append((b-a).total_seconds()/3600)
        index_stats.append({'day':p.parent.name,'tokens':len(mi),'markets':len(uniq),
                            'assets_per_market':dict(Counter(token_counts.values())),
                            'start_min':min((v.get('start_time') for v in uniq.values() if v.get('start_time')),default=None),
                            'start_max':max((v.get('start_time') for v in uniq.values() if v.get('start_time')),default=None),
                            'listing_to_end_hours':quant(durations)})
        for aid in needed & mi.keys():labels[aid]=mi[aid]
    descriptive=[];union_labels={}
    for i,rr in enumerate(rows):
        cats=Counter();weighted=Counter()
        for r in rr:
            matches=[labels[a] for a in r['asset_ids'] if a in labels]
            cat=category(' '.join((matches[0].get(k) or '') for k in ['question','event_title'])) if matches else 'Unmapped'
            cats[cat]+=1;weighted[cat]+=r['updates']+r['trades']+r['book_levels']
            union_labels[r['market']]=cat
        descriptive.append({'sample':i,'categories':cats,'rows_by_category':weighted})
    mf=manifest();primary={p:v for p,v in mf.items() if re.match(r'^raw/\d{4}-\d{2}-\d{2}/.*\.jsonl\.zst$',p)}
    bymonth={}
    for month in ['2026-05','2026-06','2026-07','2026-08']:
        vv=[v['bytes'] for p,v in primary.items() if p.split('/')[1].startswith(month)]
        bymonth[month]={'objects':len(vv),'total_bytes':sum(vv),'object_bytes':quant(vv)}
    days={p.split('/')[1] for p in primary};missing=[]
    d=date.fromisoformat(min(days));end=date.fromisoformat(max(days))
    while d<=end:
        if str(d) not in days:missing.append(str(d))
        d+=timedelta(days=1)
    policy_data=[];liquidity=[]
    # Recompute all policies so there is no dependence on analysis-code version.
    for i,rr in enumerate(rows):
        early=sorted([r for r in rr if r['early_messages']],key=lambda r:(-r['early_updates'],r['market']))
        selected={
            '2+ updates':{r['market'] for r in early if r['early_updates']>=2},
            '10+ updates':{r['market'] for r in early if r['early_updates']>=10},
            '50+ updates':{r['market'] for r in early if r['early_updates']>=50},
            '10+ and spread <=5c':{r['market'] for r in early if r['early_updates']>=10 and r['median_early_spreads'] is not None and r['median_early_spreads']<=.0500001},
            'Top 10% prior activity':{r['market'] for r in early[:max(1,math.ceil(len(early)*.1))]},
            'Stable random 10%':{r['market'] for r in early if int(hashlib.sha256(('20260925'+r['market']).encode()).hexdigest()[:8],16)/2**32<.1}}
        all_late=sum(r['late_rows'] for r in rr)
        for name,ids in selected.items():policy_data.append({'sample':i,'policy':name,'selected':len(ids),
                    'market_pct':pct(len(ids),len(rr)),'late_rows_pct':pct(sum(r['late_rows'] for r in rr if r['market'] in ids),all_late)})
        liquidity.append({'sample':i,'markets':len(rr),'no_trades_pct':pct(sum(r['trades']==0 for r in rr),len(rr)),
                          'valid_spread_markets':sum(r['median_spreads'] is not None for r in rr),
                          'spread':quant([r['median_spreads'] for r in rr if r['median_spreads'] is not None]),
                          'depth_markets':sum(r['median_depth'] is not None for r in rr),
                          'depth_shares':quant([r['median_depth'] for r in rr if r['median_depth'] is not None])})
    groups={'Early broad (0-2)':range(3),'Later prefixes (3-11)':range(3,12),'Aug16 interiors (12-15)':range(12,16)}
    policies=[];storage=[];panel_groups=[]
    panel=[r for i in range(16) for r in read(RESULTS/f'category_panel_{i:02d}.json')]
    for group,ix in groups.items():
        for name in selected:
            pp=[p for p in policy_data if p['sample'] in ix and p['policy']==name]
            policies.append({'group':group,'policy':name,'market_pct_median':statistics.median(p['market_pct'] for p in pp),
                             'late_rows_pct_median':statistics.median(p['late_rows_pct'] for p in pp),
                             'late_rows_pct_min':min(p['late_rows_pct'] for p in pp),'late_rows_pct_max':max(p['late_rows_pct'] for p in pp)})
        ss=[samples[i] for i in ix];raw=sum(s['recompressed_complete_json_bytes'] for s in ss)
        z3=sum(sum(s['parquet_bytes']['3'].values()) for s in ss);z9=sum(sum(s['parquet_bytes']['9'].values()) for s in ss)
        storage.append({'group':group,'json_zstd3_bytes':raw,'parquet_zstd3_bytes':z3,'parquet_zstd9_bytes':z9,
                        'ratio_z3':z3/raw,'ratio_z9':z9/raw,'z9_saving_pct':pct(z3-z9,z3),
                        'z3_write_seconds':sum(s['compression_seconds']['3'] for s in ss),
                        'z9_write_seconds':sum(s['compression_seconds']['9'] for s in ss)})
        pp=[r for r in panel if r['sample'] in ix]
        durations=[];event_durations=[];created_age=[];tokens=Counter()
        for r in pp:
            a,b,e,c=dt(r['start']),dt(r['end']),dt(r['event_start']),dt(r['created'])
            if a and b and b>=a:durations.append((b-a).total_seconds()/3600)
            if e and b and b>=e:event_durations.append((b-e).total_seconds()/3600)
            if c:created_age.append((samples[r['sample']]['receive_start_ms']/1000-c.timestamp())/86400)
            if r['token_ids']:tokens[len(json.loads(r['token_ids']))]+=1
        panel_groups.append({'group':group,'draws':len(pp),'categories':Counter(r['category'] for r in pp),
                             'listing_to_end_hours':quant(durations),'event_start_to_end_hours':quant(event_durations),
                             'age_at_sample_days':quant(created_age),'token_counts':tokens})
    downloads=[json.loads(line) for line in (RESULTS/'downloads.jsonl').read_text().splitlines()]
    output={'manifest':{'objects':len(mf),'total_bytes':sum(v['bytes'] for v in mf.values()),'primary_raw_objects':len(primary),
                        'primary_raw_bytes':sum(v['bytes'] for v in primary.values()),'days':len(days),'missing_dates':missing,'by_month':bymonth},
            'sampling':{'raw_market_union':len(union),'raw_assets_union':len(needed),'union_assets_per_market':Counter(map(len,raw_assets.values())),
                        'outer_messages':sum(s['outer_messages'] for s in samples),'duplicates':sum(s['duplicates'] for s in samples),
                        'schemas':dict(sum((Counter(s['schema']) for s in samples),Counter())),
                        'cached_index_market_union':len(index_ids),'cached_index_categories':Counter(category(' '.join((v.get(k) or '') for k in ['question','event_title'])) for v in index_ids.values()),
                        'raw_union_descriptive_categories':Counter(union_labels.values())},
            'index_stats':index_stats,'descriptive':descriptive,'liquidity':liquidity,'policies':policies,'policy_per_window':policy_data,
            'storage':storage,'official_category_panel':panel_groups,
            'resources':{'download_cache_bytes':sum(p.stat().st_size for p in CACHE.rglob('*') if p.is_file()),
                         'download_calls':len(downloads),'download_seconds':quant([r['seconds'] for r in downloads]),
                         'analysis_seconds':quant([s['scan_and_benchmark_seconds'] for s in samples]),
                         'api_seconds':quant([read(p)['seconds'] for p in (CACHE/'api').glob('*.json')])}}
    save(RESULTS/'summary.json',output)
    for name in ['manifest','sampling','policies','storage','official_category_panel','resources']:
        print(name,json.dumps(output[name],indent=2))

if __name__=='__main__':main()
