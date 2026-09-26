"""One bounded 64 MiB prefix transfer, within the shared 5 GB cache budget."""
import sys,json
from probe import RESULTS,download
if __name__=='__main__':
    i=int(sys.argv[1]);s=json.loads((RESULTS/'plan.json').read_text())['samples'][i]
    p=download(s['path'],64*1024**2)
    print(i,p.name,p.stat().st_size)
