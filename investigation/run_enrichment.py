"""Bounded two-worker enrichment or local scan driver; each child has a 58s limit."""
import concurrent.futures,subprocess,sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def one(i):
    script='analyze.py' if i>=12 else 'enrich.py'
    start=time.perf_counter()
    try:
        r=subprocess.run([sys.executable,'investigation/'+script,str(i)],cwd=ROOT,capture_output=True,text=True,timeout=58)
        out={'sample':i,'script':script,'seconds':round(time.perf_counter()-start,2),'exit':r.returncode}
        if r.returncode:out['error']=r.stderr[-500:]
    except subprocess.TimeoutExpired:out={'sample':i,'timeout':58}
    print(json.dumps(out),flush=True)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(one,[int(x) for x in sys.argv[1:]]))
