"""Run a script on sample indices, two processes maximum and 58s per child."""
import subprocess,concurrent.futures,json,time,sys
from probe import ROOT,RESULTS
def one(task):
    script,arg=task;start=time.perf_counter()
    try:
        r=subprocess.run([sys.executable,'investigation/'+script,str(arg)],cwd=ROOT,capture_output=True,text=True,timeout=58)
        result={'script':script,'arg':arg,'seconds':round(time.perf_counter()-start,2),'exit':r.returncode,
                'output':r.stdout[-1800:],'error':r.stderr[-500:] if r.returncode else None}
    except subprocess.TimeoutExpired:result={'script':script,'arg':arg,'timeout':58}
    print(json.dumps(result),flush=True)
    return result
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(one,[(sys.argv[1],int(i)) for i in sys.argv[2:]]))
    with (RESULTS/'bounded_jobs.jsonl').open('a') as out:
        for r in results:out.write(json.dumps(r)+'\n')
