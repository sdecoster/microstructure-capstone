"""Bounded, restartable real-data investigation. All downloads stay under data/market_filter_investigation.

Run individual commands from project root. Never prints signed URLs.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, random, re, time, uuid
from contextlib import contextmanager
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import requests
import zstandard as zstd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/market_filter_investigation'
RESULTS = ROOT / 'investigation/results'
MANIFEST = ROOT / 'poly-data-share/poly-data-share/manifest.tsv'
BUDGET = 5_000_000_000
SEED = 20260925

@contextmanager
def reserve_storage(additional_bytes):
    """Cross-process admission guard. Concurrent transfers cannot oversubscribe the cap.

    Reservations overcount bytes already written by ongoing transfers, deliberately
    conservatively. An interrupted process may leave a reservation: fail closed.
    """
    CACHE.mkdir(parents=True,exist_ok=True)
    folder=CACHE/'.reservations';folder.mkdir(exist_ok=True)
    lock=CACHE/'.budget-lock';started=time.perf_counter()
    while True:
        try:lock.mkdir();break
        except FileExistsError:
            if time.perf_counter()-started>2:raise TimeoutError('Storage admission lock busy; retry explicitly')
            time.sleep(.02)
    claim=folder/(uuid.uuid4().hex+'.json')
    try:
        used=sum(p.stat().st_size for p in CACHE.rglob('*') if p.is_file() and folder not in p.parents)
        reserved=sum(int(p.read_text()) for p in folder.glob('*.json'))
        if used+reserved+additional_bytes>BUDGET:raise RuntimeError('5 GB investigation storage budget exhausted')
        claim.write_text(str(additional_bytes),encoding='ascii')
    finally:lock.rmdir()
    try:yield
    finally:claim.unlink(missing_ok=True)

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True), encoding='utf-8')

def manifest():
    with MANIFEST.open(encoding='utf-8') as f:
        return {p: {'bytes': int(n), 'url': u} for n,p,u in csv.reader(f, delimiter='\t')}

def plan():
    rows = manifest()
    # Calendar strata cover the bulk-size transition and late/early archive.
    strata = [('2026-05-23','2026-05-27'),('2026-05-28','2026-06-01'),
              ('2026-06-02','2026-06-04'),('2026-06-18','2026-06-24'),
              ('2026-06-25','2026-07-01'),('2026-07-02','2026-07-08'),
              ('2026-07-09','2026-07-15'),('2026-07-16','2026-07-22'),
              ('2026-07-23','2026-07-29'),('2026-07-30','2026-08-05'),
              ('2026-08-06','2026-08-12'),('2026-08-13','2026-08-16')]
    rng = random.Random(SEED)
    selected = []
    for a,b in strata:
        candidates = sorted(p for p in rows if re.fullmatch(r'raw/\d{4}-\d{2}-\d{2}/\d{2}00.jsonl.zst',p)
                            and a <= p.split('/')[1] <= b)
        p = rng.choice(candidates)  # no size/liquidity-based selection
        selected.append({'path':p,'bytes':rows[p]['bytes'],'stratum':[a,b],
                         'index':f"raw/_index/{p.split('/')[1]}/polymarket_index.json"})
    local_rng = random.Random(919)
    for hour in ['1500','1600','2000','2100']:
        p=f'raw/2026-08-16/{hour}.jsonl.zst'
        selected.append({'path':p,'local':f'data/exploration_sample/{p}',
                         'index':'raw/_index/2026-08-16/polymarket_index.json',
                         'start_fraction':round(local_rng.uniform(.2,.8),3),
                         'stratum':['local_within_hour_supplement']})
    save(RESULTS/'plan.json', {'seed':SEED,'prefix_bytes':8*1024**2,'samples':selected})
    return selected

def download(path, size=None):
    entry=manifest()[path];n=min(entry['bytes'],size) if size else entry['bytes']
    target=CACHE/(path+(f'.prefix-{n}' if n<entry['bytes'] else ''))
    if target.exists() and target.stat().st_size==n:return target
    partial=target.with_name(target.name+'.part')
    offset=partial.stat().st_size if partial.exists() else 0
    with reserve_storage(n-offset):return _download(path,size)

def _download(path, size=None):
    entry = manifest()[path]
    n = min(entry['bytes'], size) if size else entry['bytes']
    target = CACHE / (path + (f'.prefix-{n}' if n < entry['bytes'] else ''))
    if target.exists() and target.stat().st_size == n:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    offset = partial.stat().st_size if partial.exists() else 0
    used = sum(p.stat().st_size for p in CACHE.rglob('*') if p.is_file())
    if used + n - offset > BUDGET:
        raise RuntimeError('Investigation download budget exhausted')
    start = time.perf_counter()
    try:
        while offset < n:
            if time.perf_counter()-start > 40:
                raise TimeoutError('40s transfer budget reached; partial retained for explicit resume')
            end = min(n,offset+2*1024**2)-1
            with requests.get(entry['url'],headers={'Range':f'bytes={offset}-{end}', 'Accept-Encoding':'identity'},
                              stream=True, timeout=(5,8)) as response:
                if response.status_code != 206:
                    raise RuntimeError(f'Range request returned HTTP {response.status_code}; body not read')
                expected = f'bytes {offset}-{end}/{entry["bytes"]}'
                if response.headers.get('Content-Range') != expected:
                    raise RuntimeError('Content-Range mismatch')
                copied = 0
                with partial.open('ab') as out:
                    for chunk in response.iter_content(128*1024):
                        copied += len(chunk)
                        if copied > end-offset+1: raise RuntimeError('Oversized range response')
                        out.write(chunk)
                        if time.perf_counter()-start > 48: raise TimeoutError('48s download deadline')
                if copied != end-offset+1: raise RuntimeError('Short range response')
            offset = end+1
        partial.replace(target)
    finally:
        RESULTS.mkdir(parents=True,exist_ok=True)
        with (RESULTS/'downloads.jsonl').open('a',encoding='utf-8') as log:
            log.write(json.dumps({'path':path,'requested_bytes':n,'stored_bytes':target.stat().st_size if target.exists() else partial.stat().st_size if partial.exists() else 0,
                                  'seconds':round(time.perf_counter()-start,3), 'complete':target.exists()})+'\n')
    return target

def records(path, max_lines=100_000, deadline=40, start_fraction=0):
    start=time.perf_counter()
    with path.open('rb') as raw, zstd.ZstdDecompressor().stream_reader(raw) as reader:
        if start_fraction:
            # Decompress and discard in bounded chunks; no JSON parsing while seeking.
            # Compressed fractions are NOT uniform time samples. Report actual timestamps.
            target=int(path.stat().st_size*start_fraction)
            while raw.tell()<target:
                if time.perf_counter()-start>deadline:raise TimeoutError('Skip deadline')
                if not reader.read(1024**2):return
        with io.TextIOWrapper(reader,encoding='utf-8') as stream:
            if start_fraction:stream.readline()  # discard partial boundary line
            for i,line in enumerate(stream,1):
                if i > max_lines or time.perf_counter()-start > deadline: break
                if not line.endswith('\n'): break  # incomplete final prefix line
                yield i,json.loads(line)

def inspect(sample):
    selected=json.loads((RESULTS/'plan.json').read_text())['samples'][sample]
    p=download(selected['path'],8*1024**2)
    schema=Counter();examples={}
    for i,o in records(p,5000):
        c=o.get('content',o)
        if isinstance(c,str):
            try:c=json.loads(c)
            except ValueError:c={}
        typ=c.get('event_type',o.get('message_type','unknown')) if isinstance(c,dict) else type(c).__name__
        schema[typ]+=1
        if typ not in examples: examples[typ]={'outer_keys':list(o),'content':str(c)[:1800]}
    print(json.dumps({'path':selected['path'],'schemas':schema,'examples':examples},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['plan','inspect','index','fetch'])
    parser.add_argument('--sample',type=int,default=0)
    args=parser.parse_args()
    if args.command=='plan': print(json.dumps(plan(),indent=2))
    elif args.command=='inspect':inspect(args.sample)
    else:
        s=json.loads((RESULTS/'plan.json').read_text())['samples'][args.sample]
        p=download(s['index'] if args.command=='index' else s['path'],None if args.command=='index' else 8*1024**2)
        print(str(p.relative_to(ROOT)),p.stat().st_size)
