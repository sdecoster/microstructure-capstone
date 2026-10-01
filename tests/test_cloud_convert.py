from pathlib import Path
import sys
import pytest
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"investigation"))
from cloud_convert import SCALE,Writer,_scale_text,fingerprint,rows,scale
def test_exact_scale_and_precision_rejection():
 assert scale("0.123456","price")==123456
 assert scale("1","size")==SCALE
 with pytest.raises(ValueError):scale("0.0000001","price")
def test_tick_size_is_preserved():
 assert rows({"event_type":"tick_size_change","market":"m","asset_id":"a","old_tick_size":"0.01","new_tick_size":"0.001"},"s",1)[0][1]["new_tick_size_i"]==1000
def test_other_event_is_audited():
 assert rows({"event_type":"unknown","market":"m"},"s",1)[0][0]=="other_feed_events"

def test_staged_writer_creates_parquet_part():
 with TemporaryDirectory() as temp:
  writer=Writer(Path(temp),'2026-08-16','source',1)
  writer.add('price_changes',{'market_key':'00','source_id':'source','price_i':1})
  writer.close()
  assert len(list(Path(temp).rglob('*.parquet')))==1

def test_exact_raw_payload_fingerprint_preserves_exact_dedupe_scope():
 assert fingerprint('{"a":1}',{'a':1})==fingerprint('{"a":1}',{'a':1})
 assert fingerprint('{"a":1}',{'a':1})!=fingerprint('{ "a": 1 }',{'a':1})
def test_scale_accepts_padding_but_rejects_nonzero_excess_precision():
 assert scale('-1.2','value')==-1200000
 assert scale('0.1000000','value')==100000
 with pytest.raises(ValueError):scale('0.1000001','value')
def test_scale_cache_keeps_exact_values():
 assert _scale_text("0.500000")==500000
 assert _scale_text("0.500000")==500000