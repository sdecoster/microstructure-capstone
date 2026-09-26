"""Small index queries around observed recording breaks."""
import sys
from probe import download,manifest
if __name__=='__main__':
    d=['2026-06-04','2026-06-18','2026-06-19','2026-07-16','2026-07-17'][int(sys.argv[1])]
    p=f'raw/_index/{d}/polymarket_index.json'
    if p in manifest():print(download(p))
    else:print('Not in manifest:',p)
