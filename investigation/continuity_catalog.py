"""Recurring families and recording-regime evidence from real cached data."""
import json,re,statistics,time
from collections import Counter,defaultdict
from datetime import datetime
from probe import CACHE,RESULTS,ROOT,manifest,save
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def stamp(s):
    try:return datetime.fromisoformat(re.sub(r'(\.\d{6})\d+',r'\1',s.replace('Z','+00:00'))).timestamp()
    except (ValueError,TypeError,AttributeError):return None
def family(v):
    slug=v.get('event_slug') or v.get('slug') or ''
    title=' '.join(str(v.get(k) or '') for k in ['event_title','question'])
    crypto={'bitcoin':'BTC','btc':'BTC','ethereum':'ETH','eth':'ETH','solana':'SOL','sol':'SOL','xrp':'XRP','bnb':'BNB','dogecoin':'DOGE','doge':'DOGE','hyperliquid':'HYPE','hype':'HYPE','zcash':'ZEC','zec':'ZEC'}
    m=re.search(r'^(btc|eth|sol|xrp|bnb|doge|hype|zec)-updown-(5m|15m|1h|4h)-',slug)
    if m:return f'{crypto[m[1]]} {m[2]}'
    m=re.search(r'^(bitcoin|ethereum|solana|xrp|bnb|dogecoin|hyperliquid|zcash)-up-or-down-',slug)
    if m:
        a,b=stamp(v.get('eventStartTime')),stamp(v.get('endDate') or v.get('end_time'))
        duration=round((b-a)/60) if a and b else None
        if duration in [5,15,60,240]:return f'{crypto[m[1]]} '+{5:'5m',15:'15m',60:'1h',240:'4h'}[duration]
        if re.search(r'\d+(am|pm)(-|$)',slug):return f'{crypto[m[1]]} 1h'
        return f'{crypto[m[1]]} up/down other'
    sports={'mlb':'MLB','nba':'NBA','wnba':'WNBA','nhl':'NHL','nfl':'NFL','atp':'ATP tennis','wta':'WTA tennis','itf':'ITF tennis','ucl':'UEFA Champions League','epl':'English Premier League','lol':'League of Legends','cs2':'Counter-Strike','dota2':'Dota 2','fifa':'World Cup','wc':'World Cup'}
    for prefix,label in sports.items():
        if slug.startswith(prefix+'-'):return label
    if 'temperature' in title.lower():return 'Weather temperature'
    if re.search(r'\b(say|mention|mentions)\b',title,re.I):return 'Mentions'
    return 'Other'
def run():
    started=time.perf_counter();n=sum('calibration_replacement_of' not in s for s in load(RESULTS/'plan.json')['samples'])
    raw=[load(RESULTS/f'markets_{i:02d}.json') for i in range(n)]
    needed={a for rr in raw for r in rr for a in r['asset_ids']};byasset={};daystats=[]
    paths=list((CACHE/'raw/_index').glob('*/polymarket_index.json'))+[ROOT/'data/exploration_sample/raw/_index/2026-08-16/polymarket_index.json']
    for p in sorted(set(paths)):
        x=load(p);day=p.parent.name;at=stamp(x['generated_at']);mi=x['market_index'];uniq={v['market_id']:v for v in mi.values()}
        ages=[(at-stamp(v['start_time']))/86400 for v in uniq.values() if stamp(v.get('start_time')) is not None]
        daystats.append({'date':day,'markets':len(uniq),'age_days_median':statistics.median(ages),
                         'age_gt2d':sum(x>2 for x in ages),'age_gt7d':sum(x>7 for x in ages),'age_max':max(ages),
                         'families':Counter(family(v) for v in uniq.values()),'schema_version':x.get('version')})
        for a in needed&mi.keys():byasset[a]=mi[a]
    bycondition={}
    for p in (CACHE/'api').glob('*.json'):
        x=load(p).get('data');ms=x if isinstance(x,list) else [x] if isinstance(x,dict) else []
        for m in ms:
            if isinstance(m,dict) and m.get('conditionId'):
                ev=(m.get('events') or [{}])[0]
                bycondition[m['conditionId']]={**m,'event_slug':ev.get('slug') or m.get('slug'),'event_title':ev.get('title')}
    candidates=[];windows=[]
    for i,rr in enumerate(raw):
        out=[]
        for r in rr:
            v=bycondition.get(r['market']) or next((byasset[a] for a in r['asset_ids'] if a in byasset),{})
            out.append({**r,'metadata':v,'family':family(v) if v else 'Unmapped'})
        windows.append({'sample':i,'families':dict(Counter(r['family'] for r in out)),
                        'updates_by_family':dict(sum((Counter({r['family']:r['updates']}) for r in out),Counter())),
                        'top':[{k:r[k] for k in ['market','family','updates','trades','metadata']} for r in sorted(out,key=lambda r:-r['updates'])[:25]]})
        candidates.append({'sample':i,'markets':[r['market'] for r in sorted(rr,key=lambda r:-r['updates'])[:30]]})
        save(RESULTS/f'family_markets_{i:02d}.json',out)
    daily=defaultdict(list)
    for p,e in manifest().items():
        if re.fullmatch(r'raw/\d{4}-\d{2}-\d{2}/\d{2}00.jsonl.zst',p):daily[p.split('/')[1]].append(e['bytes'])
    save(RESULTS/'continuity_catalog.json',{'days':daystats,'windows':windows,'candidate_api':candidates,
          'daily_raw':[{'date':d,'hours':len(v),'median_GB':statistics.median(v)/1e9,'total_GB':sum(v)/1e9} for d,v in sorted(daily.items())],
          'seconds':time.perf_counter()-started})
    print('Catalogue rebuilt in',round(time.perf_counter()-started,2),'seconds')
    print('Index age evidence',[(d['date'],d['markets'],round(d['age_days_median'],2),d['age_gt2d']) for d in daystats])
    print('Activity leaders',ascii([(w['sample'],[(r['family'],r['metadata'].get('question'),r['updates']) for r in w['top'][:3]]) for w in windows]))
if __name__=='__main__':run()
