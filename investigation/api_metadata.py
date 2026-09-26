"""Small official-API metadata probes; responses are current observations, not historical truth."""
import json, random, time
from datetime import datetime,timezone
import requests
from probe import CACHE, RESULTS, save, reserve_storage

def fetch(label,url,params=None):
    target=CACHE/'api'/f'{label}.json'
    if target.exists():return json.loads(target.read_text())
    start=time.perf_counter()
    result={'url':url,'params':params,'fetched_at':datetime.now(timezone.utc).isoformat()}
    try:
        with requests.get(url,params=params,stream=True,timeout=(5,8)) as r:
            result['status']=r.status_code;body=bytearray()
            for chunk in r.iter_content(65536):
                if len(body)+len(chunk)>2*1024**2:raise RuntimeError('2 MiB response limit')
                body.extend(chunk)
                if time.perf_counter()-start>35:raise TimeoutError('35s API deadline')
            result['bytes']=len(body)
            try:result['data']=json.loads(body)
            except ValueError:result['error']='non-JSON response'
    except Exception as e:result['error']=type(e).__name__
    result['seconds']=round(time.perf_counter()-start,3)
    serialized_bytes=len(json.dumps(result,indent=2,ensure_ascii=True).encode('utf-8'))
    with reserve_storage(serialized_bytes):save(target,result)
    print(label,result.get('status'),result.get('bytes'),result['seconds'],flush=True)
    return result

if __name__=='__main__':
    all_results=[]
    for cat in ['sports','crypto','mentions','politics','weather']:
        all_results.append(fetch('tag_'+cat,'https://gamma-api.polymarket.com/tags/slug/'+cat))
    for sample in [0,3,11]:
        p=RESULTS/f'markets_{sample:02d}.json'
        if not p.exists():continue
        markets=json.loads(p.read_text());rng=random.Random(20260925+sample)
        for j,m in enumerate(rng.sample(markets,min(2,len(markets)))):
            for closed in ['false','true']:
                all_results.append(fetch(f'market_{sample}_{j}_{closed}','https://gamma-api.polymarket.com/markets',
                                         {'condition_ids':m['market'],'closed':closed,'limit':2,'include_tag':'true'}))
    all_results.append(fetch('id_3616667','https://gamma-api.polymarket.com/markets/3616667'))
    all_results.append(fetch('tags_control','https://gamma-api.polymarket.com/tags',{'limit':3}))
    save(RESULTS/'api_summary.json',[{k:v for k,v in r.items() if k!='data'}|{'result_count':len(r['data']) if isinstance(r.get('data'),list) else None,
                                                                     'keys':list(r['data']) if isinstance(r.get('data'),dict) else None} for r in all_results])
