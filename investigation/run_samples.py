"""Run bounded independent probes, enforcing a 58s watchdog per child command.

One remote object or one analysis per child; continue and report failures.
"""
import concurrent.futures, json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def one(i):
    for args in [['investigation/probe.py','index','--sample',str(i)],['investigation/analyze.py',str(i)]]:
        start=time.perf_counter()
        try:
            r=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,timeout=58)
            status={'sample':i,'command':args[0]+(' index' if 'index' in args else ''),'seconds':round(time.perf_counter()-start,2),'exit':r.returncode}
            if r.returncode:status['error']=r.stderr[-500:]
        except subprocess.TimeoutExpired:status={'sample':i,'command':args[0],'timeout':58}
        print(json.dumps(status),flush=True)
if __name__=='__main__':
    indices=[int(x) for x in sys.argv[1:]] or list(range(12))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(one,indices))
