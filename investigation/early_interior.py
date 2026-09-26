"""Extend just three early prefixes to 128 MiB, reusing their existing 64 MiB.

No whole-hour download. All additions remain inside the shared cache cap.
"""
import sys,shutil
from datetime import datetime,timezone
import pytz
from probe import CACHE,RESULTS,ROOT,download,reserve_storage,save
from continuity_catalog import load
from api_metadata import fetch
def run(i):
    plan=load(RESULTS/'plan.json');s=plan['samples'][i];source=CACHE/(s['path']+'.prefix-67108864')
    target=CACHE/(s['path']+'.prefix-134217728');part=target.with_name(target.name+'.part')
    if not target.exists() and not part.exists():
        with reserve_storage(source.stat().st_size):shutil.copyfile(source,part)
    p=download(s['path'],128*1024**2)
    epoch=load(RESULTS/f'sample_{i:02d}.json')['receive_start_ms']//1000
    local=datetime.fromtimestamp(epoch,timezone.utc).astimezone(pytz.timezone('America/New_York'))
    suffix=f'{local.strftime("%B").lower()}-{local.day}-{local.year}-{local.hour%12 or 12}{"am" if local.hour<12 else "pm"}-et'
    slugs=[f'{coin}-up-or-down-{suffix}' for coin in ['bitcoin','ethereum','solana','xrp']]
    slugs += [f'{coin}-updown-4h-{epoch//14400*14400}' for coin in ['btc','eth','sol','xrp']]
    for closed in ['false','true']:
        fetch(f'early_current_slow_{i}_{closed}','https://gamma-api.polymarket.com/markets',
              [('slug',v) for v in slugs]+[('closed',closed),('limit',len(slugs))])
    print(i,'extended bytes',p.stat().st_size)
if __name__=='__main__':run(int(sys.argv[1]))
