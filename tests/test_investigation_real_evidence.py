"""Validate saved results of bounded real-source probes; no generated market data."""
import json
from pathlib import Path
import pytest

RESULTS=Path(__file__).resolve().parents[1]/'investigation/results'

@pytest.fixture(scope='module')
def observations():
    paths=[RESULTS/f'sample_{i:02d}.json' for i in range(16)]
    if not all(p.exists() for p in paths):pytest.skip('Real investigation results are not available')
    return [json.loads(p.read_text()) for p in paths]

def test_real_compact_tables_round_trip_at_both_compression_levels(observations):
    for s in observations:
        assert s['parquet_round_trip_verified'] is True
        assert set(s['round_trip_seconds'])=={'3','9'}
        for level in ['3','9']:
            assert s['parquet_bytes'][level]['assets']>0
            assert s['parquet_bytes'][level]['markets']>0

def test_real_probe_decisions_have_fixed_forward_elapsed_time(observations):
    for s in observations:
        assert s['decision_seconds']==(20 if s['sample']>=12 else 1)
        assert s['receive_start_ms']+1000*s['decision_seconds']<s['receive_end_ms']
        assert s['outer_messages']<=100000
        assert all(0<=p['late_rows']<=p['all_late_rows'] for p in s['policies'])

def test_real_asset_relationships_are_consistent_across_windows(observations):
    owner={};by_market={}
    for s in observations:
        rows=json.loads((RESULTS/f"markets_{s['sample']:02d}.json").read_text())
        for r in rows:
            for aid in r['asset_ids']:
                assert owner.setdefault(aid,r['market'])==r['market']
                by_market.setdefault(r['market'],set()).add(aid)
    assert len(by_market)==29694
    assert all(len(v)==2 for v in by_market.values())

def test_official_panel_joins_requested_real_markets(observations):
    for s in observations:
        i=s['sample'];path=RESULTS/f'category_panel_{i:02d}.json'
        if not path.exists():pytest.skip('Cached real API panel not available')
        panel=json.loads(path.read_text())
        raw={r['market']:set(r['asset_ids']) for r in json.loads((RESULTS/f'markets_{i:02d}.json').read_text())}
        assert len(panel)==16
        for p in panel:
            assert set(json.loads(p['token_ids']))==raw[p['market']]
