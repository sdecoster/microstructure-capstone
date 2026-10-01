"""Validate parallel planning against the supplied real archive manifest."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "investigation"))

from cloud_archive_transfer import read_manifest
from cloud_parallel_plan import build_plan, classify_source

def test_real_regular_hours_are_balanced_and_special_sources_are_retained():
    sources = []
    for row in read_manifest():
        source = classify_source("gs://raw/" + row.destination_object, row.size)
        if source is not None:
            sources.append(source)
    plan = build_plan(sources, workers=4)
    assert plan["regular_sources"] == 1691
    assert plan["regular_bytes"] == 2906585311256
    assert plan["nonstandard_sources"]
    assert sum(worker["bytes"] for worker in plan["workers"]) == plan["regular_bytes"]
    loads = [worker["bytes"] for worker in plan["workers"]]
    assert max(loads) - min(loads) < max(source.size_bytes for source in sources)

def test_only_regular_hour_paths_are_auto_scheduled():
    assert classify_source("gs://raw/control/urls.tsv", 1) is None
    special = classify_source("gs://raw/x/raw/2026-07-17/recovered.jsonl.zst", 1)
    assert special is not None and special.kind == "nonstandard_raw"


def test_bounded_production_pilot_selects_latest_real_sources():
    from cloud_convert import selected_work
    import pytest
    sources = [classify_source('gs://raw/' + row.destination_object, row.size)
               for row in read_manifest()]
    plan = build_plan([source for source in sources if source is not None], workers=2)
    work = selected_work(plan, max_sources=2)
    assert [(source.date, source.hour) for source in work] == [('2026-08-16', '2100'), ('2026-08-16', '2000')]
    left = {source.uri for source in selected_work(plan, [0])}
    right = {source.uri for source in selected_work(plan, [1])}
    assert not left.intersection(right)
    assert len(left | right) == 1691
    with pytest.raises(ValueError):
        selected_work(plan, max_sources=0)
