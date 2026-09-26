"""Two concurrent bounded requests; a 58 second watchdog per window's API audit."""
import concurrent.futures,subprocess,sys,time,json
from probe import ROOT
def run(i):
    start=time.perf_counter()
    try:
        r=subprocess.run([sys.executable,'investigation/category_panel.py',str(i)],cwd=ROOT,
                         capture_output=True,text=True,timeout=58)
        print(json.dumps({'sample':i,'seconds':round(time.perf_counter()-start,2),'exit':r.returncode,
                          'error':r.stderr[-300:] if r.returncode else None}),flush=True)
    except subprocess.TimeoutExpired:print(i,'timeout at 58s',flush=True)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,range(16)))
