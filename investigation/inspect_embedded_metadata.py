"""Inspect rare embedded metadata in an already cached prefix, with a 20s cap."""
import json
from probe import CACHE,RESULTS,records,save

if __name__=='__main__':
    p=CACHE/'raw/2026-07-30/2100.jsonl.zst.prefix-8388608'
    found={}
    for seq,o in records(p,max_lines=100000,deadline=20):
        c=o.get('content')
        if isinstance(c,str):
            try:c=json.loads(c)
            except ValueError:continue
        typ=o.get('message_type')
        if typ in ['token_index','market_metadata','event_metadata'] and typ not in found:
            found[typ]={'sequence':seq,'outer_keys':list(o),'receive_timestamp':o.get('timestamp'),
                        'content_type':type(c).__name__,'keys':list(c)[:40] if isinstance(c,dict) else None,
                        'preview':str(c)[:2200]}
        if len(found)==3:break
    save(RESULTS/'embedded_metadata.json',found)
    print(json.dumps(found,indent=2))
