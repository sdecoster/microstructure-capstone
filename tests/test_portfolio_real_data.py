"""Real-source checks for the revised investigation; no synthetic fixtures."""
import json
from decimal import Decimal
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'investigation'))
from portfolio_probe import scaled,reader

def results():
    paths=[ROOT/f'investigation/results/portfolio_{i:02d}.json' for i in range(23)]
    if not all(p.exists() for p in paths):pytest.skip('Real portfolio evidence is not available')
    return [json.loads(p.read_text()) for p in paths]

def test_real_portfolio_round_trips_and_family_subset_rows():
    for s in results():
        assert s['round_trip_verified'] is True
        assert s['numeric_scale']==1000000
        p=s['portfolios']
        assert p['crypto15m4']['rows']<=p['crypto15m1h8']['rows']<=p['crypto_slow12']['rows']<=p['crypto_all16']['rows']
        assert p['sports5']['rows']<=p['sports15']['rows']
        assert s['post_compressed_bytes_approx']>0 and s['post_seconds']>0

def test_scaled_numbers_equal_actual_source_values():
    path=ROOT/'data/market_filter_investigation/raw/2026-05-25/0800.jsonl.zst.prefix-67108864'
    if not path.exists():pytest.skip('Real prefix not available')
    checked=0
    for seq,o,_,_ in reader(path):
        c=o.get('content')
        if isinstance(c,str):c=json.loads(c)
        if not isinstance(c,dict):continue
        rows=c.get('price_changes',[])+c.get('bids',[])+c.get('asks',[])+[c]
        for r in rows:
            for k in ['price','size','best_bid','best_ask','fee_rate_bps']:
                if r.get(k) is not None:
                    assert Decimal(scaled(r[k]))/Decimal(1000000)==Decimal(str(r[k]))
                    checked+=1
        if seq>=500:break
    assert checked>100

def test_cost_calibration_uses_real_post_rollover_windows():
    results()
    summary=json.loads((ROOT/'investigation/results/portfolio_summary.json').read_text())
    for cost in summary['costs'].values():
        assert [s['sample'] for s in cost['strata'][:3]]==[20,21,22]
        assert sum(s['raw_GB'] for s in cost['strata'])==pytest.approx(summary['raw_GB'])
        assert cost['archive_GB']==pytest.approx(cost['early_GB']+cost['later_GB'])
