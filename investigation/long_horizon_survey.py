# Historical long-horizon/event-excluded market survey. Real saved data only.
import argparse,hashlib,json,re,statistics
from collections import defaultdict
from datetime import datetime,timezone
from continuity_catalog import load,stamp
from portfolio_probe import reader
from probe import CACHE,RESULTS,ROOT,save

NOTIONAL_SAMPLES=list(range(20))
CUTOFF_HOURS=[1,6,24,48]
def first(m,*ks):return next((m[k] for k in ks if m.get(k) not in (None,'')),None)
def txt(m):return ' '.join(str(first(m,k) or '') for k in ['event_slug','slug','event_title','question']).lower()
def theme(m):
    s=txt(m)
    if re.search(r'\b(say|says|mention|mentions|mentioned)\b|number of posts|truth social|tweet',s):return 'Mentions'
    if re.search(r'temperature|weather|rainfall|snowfall|hurricane|tornado',s):return 'Weather'
    leagues=[('MLB',r'(^|\b)mlb\b|major league baseball|world series'),('NBA',r'(^|\b)nba\b'),
      ('WNBA',r'(^|\b)wnba\b'),('NFL',r'(^|\b)nfl\b|super bowl'),('NHL',r'(^|\b)nhl\b|stanley cup'),
      ('Soccer',r'premier league|champions league|world cup|\bsoccer\b|\bfifa\b|\bepl\b|\bucl\b'),
      ('Tennis',r'\batp\b|\bwta\b|\bitf\b|wimbledon|roland garros|us open tennis|australian open'),
      ('Esports',r'counter-strike|\bcs2\b|league of legends|\blol\b|dota'),
      ('F1',r'formula 1|\bf1\b'),('Golf',r'\bpga\b|golf|masters winner'),('UFC',r'\bufc\b')]
    for league,p in leagues:
        if re.search(p,s):
            game=bool(re.search(r'\bvs\.?\b|exact score|halftime|game [0-9]|map [0-9]|set [0-9]|spread|moneyline|total points',s))
            return 'Sports '+('game' if game else 'future')+': '+league
    if re.search(r'bitcoin|\bbtc\b|ethereum|\beth\b|solana|\bsol\b|\bxrp\b|crypto|dogecoin|\bdoge\b',s):return 'Crypto dated/threshold'
    if re.search(r'election|president|senate|house of representatives|governor|mayor|prime minister|parliament|congress',s):return 'Politics/elections'
    if re.search(r'fed |federal reserve|interest rate|inflation|cpi|gdp|unemployment|recession|tariff|exchange rate|wti|brent|oil price',s):return 'Macro/economics'
    if re.search(r'war|ceasefire|invasion|military|nato|strait of hormuz|missile|nuclear weapon',s):return 'Geopolitics/security'
    if re.search(r'spotify|app store|box office|youtube|billboard|album|movie|tv show',s):return 'Attention/entertainment'
    return 'Other'
def med(v):
    v=[x for x in v if x is not None]
    return statistics.median(v) if v else None
def pct(a,b):return 100*a/b if b else None
def times(m):
    listed=stamp(first(m,'startDate','start_time','createdAt'));end=stamp(first(m,'endDate','end_time'))
    return listed,stamp(first(m,'eventStartTime')),end
def catalog():
    plan=load(RESULTS/'plan.json')['samples'];obs=[];samples={}
    for i in range(min(20,len(plan))):
        fp=RESULTS/f'family_markets_{i:02d}.json';pp=RESULTS/f'portfolio_{i:02d}.json'
        sp=RESULTS/f'sample_{i:02d}.json'
        if not fp.exists() or not pp.exists() or not sp.exists():continue
        p=load(pp);window=load(sp);start_ms=window['receive_start_ms'];end_ms=window['receive_end_ms']
        at=start_ms/1000;span=window['span_seconds']
        samples[str(i)]={'source':p['source'],'at':datetime.fromtimestamp(at,timezone.utc).isoformat(),
                         'start_ms':start_ms,'end_ms':end_ms,'span_seconds':span,'survey':[]}
        for r in load(fp):
            m=r.get('metadata') or {};listed,explicit_event,end=times(m)
            if listed is None or end is None or end<=listed:continue
            duration=(end-listed)/86400;remaining=(end-at)/86400;label=theme(m)
            event=explicit_event if explicit_event is not None else end-86400 if label=='Weather' else end
            lead_hours=(event-at)/3600
            reliable=not (label.startswith('Sports game:') or label=='Mentions') or explicit_event is not None
            eligible=[h for h in CUTOFF_HOURS if duration>=2 and remaining>0 and lead_hours>=h and reliable]
            persistent=[h for h in CUTOFF_HOURS if duration>=14 and remaining>=7 and lead_hours>=h and reliable]
            x={'sample':i,'market':r['market'],'theme':label,'title':first(m,'question','event_title'),
               'duration_days':duration,'remaining_days':remaining,'event_lead_hours':lead_hours,
               'eligible_cutoff_hours':eligible,'persistent_cutoff_hours':persistent,
               'explicit_event_start':explicit_event is not None,
               'updates':r.get('updates',0),'trades':r.get('trades',0),
               'median_spread':r.get('median_spreads'),'depth':r.get('median_depth'),'span_seconds':span}
            obs.append(x)
            if eligible:samples[str(i)]['survey'].append(r['market'])
    save(RESULTS/'long_horizon_catalog.json',{'rules':{
      'cutoffs_hours':CUTOFF_HOURS,
      'eligible':'lifetime >=2d and observation precedes event anchor by cutoff',
      'persistent':'lifetime >=14d, >=7d remaining, and precedes event anchor by cutoff',
      'episodic_rule':'games/mentions require explicit eventStartTime; weather anchor is end minus 24h',
      'limit':'end is a proxy when eventStartTime is absent; production sports filters need schedules'},
      'samples':samples,'observations':obs})
    print(json.dumps({'observations':len(obs),'samples':len(samples)}))
def sample_path(i):
    s=load(RESULTS/'plan.json')['samples'][i]
    return ROOT/s['local'] if 'local' in s else CACHE/(s['path']+'.prefix-67108864')
def notional(i):
    c=load(RESULTS/'long_horizon_catalog.json');s=c['samples'][str(i)]
    wanted=set(s['survey']);out=defaultdict(lambda:{'trades':0,'notional':0.});seen=set()
    frac=load(RESULTS/'plan.json')['samples'][i].get('start_fraction',0)
    for _,o,_,_ in reader(sample_path(i),frac):
        recv=int(datetime.fromisoformat(o['timestamp'].replace('Z','+00:00')).timestamp()*1000)
        if recv<s['start_ms']:continue
        if recv>s['end_ms']:break
        x=o.get('content')
        if isinstance(x,str):
            try:x=json.loads(x)
            except ValueError:continue
        if not isinstance(x,dict) or x.get('event_type')!='last_trade_price' or x.get('market') not in wanted:continue
        h=hashlib.blake2b(json.dumps(x,sort_keys=True,separators=(',',':')).encode(),digest_size=16).digest()
        if h in seen:continue
        seen.add(h);m=x['market'];out[m]['trades']+=1;out[m]['notional']+=float(x['price'])*float(x['size'])
    save(RESULTS/f'long_horizon_notional_{i:02d}.json',{'sample':i,'markets':[{'market':m,**v} for m,v in out.items()]})
    print(json.dumps({'sample':i,'markets':len(out),'trades':sum(v['trades'] for v in out.values()),
                      'notional':sum(v['notional'] for v in out.values())}))
def group(rows):
    gs=defaultdict(list)
    for r in rows:gs[r['theme']].append(r)
    out=[]
    for name,rr in gs.items():
        spreads=[r['median_spread'] for r in rr if r['median_spread'] is not None]
        depths=[r['depth'] for r in rr if r['depth'] is not None];by=defaultdict(set)
        for r in rr:by[r['sample']].add(r['market'])
        out.append({'theme':name,'market_windows':len(rr),'unique_contracts':len({r['market'] for r in rr}),
          'sample_windows':len(by),'contracts_per_window_median':med([len(v) for v in by.values()]),
          'contracts_per_window_max':max(map(len,by.values()),default=0),'trade_market_windows':sum(r['trades']>0 for r in rr),
          'trade_market_window_pct':pct(sum(r['trades']>0 for r in rr),len(rr)),'trades':sum(r['trades'] for r in rr),
          'updates':sum(r['updates'] for r in rr),'median_updates_per_second':med([r['updates']/r['span_seconds'] for r in rr]),
          'median_spread':med(spreads),'spread_le_5c_pct':pct(sum(v<=.0500001 for v in spreads),len(spreads)),
          'markets_with_spread':len(spreads),'median_depth_within_1c_shares':med(depths),'markets_with_depth':len(depths),
          'median_duration_days':med([r['duration_days'] for r in rr]),'median_remaining_days':med([r['remaining_days'] for r in rr]),
          'leaders':[{k:r[k] for k in ['title','trades','updates','median_spread','duration_days','remaining_days']}
                     for r in sorted(rr,key=lambda x:(-x['trades'],-x['updates'],x['market']))[:8]]})
    return sorted(out,key=lambda x:(-x['trades'],-x['updates'],x['theme']))
def summary():
    c=load(RESULTS/'long_horizon_catalog.json');obs=c['observations'];ns={};scanned=[]
    for i in NOTIONAL_SAMPLES:
        p=RESULTS/f'long_horizon_notional_{i:02d}.json'
        if p.exists():
            scanned.append(i)
            for r in load(p)['markets']:ns[(i,r['market'])]=r
    cohorts={};persistent={};notionals={}
    for h in CUTOFF_HOURS:
        selected=[r for r in obs if h in r['eligible_cutoff_hours']]
        cohorts[str(h)]=group(selected)
        persistent[str(h)]=group([r for r in obs if h in r['persistent_cutoff_hours']])
        ng=defaultdict(lambda:{'market_windows':0,'trades':0,'notional':0.})
        for r in selected:
            if r['sample'] not in scanned:continue
            x=ns.get((r['sample'],r['market']),{});g=ng[r['theme']];g['market_windows']+=1
            g['trades']+=x.get('trades',0);g['notional']+=x.get('notional',0)
        notionals[str(h)]=[{'theme':k,**v} for k,v in sorted(ng.items(),key=lambda z:-z[1]['notional'])]
    out={'rules':c['rules'],'sample_count':len(c['samples']),'notional_sample_ids':scanned,
         'all_dated':group(obs),'by_cutoff_hours':cohorts,'persistent_by_cutoff_hours':persistent,
         'notional_by_cutoff_hours':notionals}
    save(RESULTS/'long_horizon_summary.json',out)
    print(json.dumps({'themes_by_cutoff':{h:len(v) for h,v in cohorts.items()},'notional_samples':scanned}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['catalog','notional','summary']);p.add_argument('--sample',type=int);a=p.parse_args()
    if a.command=='catalog':catalog()
    elif a.command=='notional':
        if a.sample is None:raise SystemExit('--sample required')
        notional(a.sample)
    else:summary()
