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
    assert plan["regular_bytes"] == 2906605106237
    assert plan["nonstandard_sources"]
    assert sum(worker["bytes"] for worker in plan["workers"]) == plan["regular_bytes"]
    loads = [worker["bytes"] for worker in plan["workers"]]
    assert max(loads) - min(loads) < max(source.size_bytes for source in sources)

def test_only_regular_hour_paths_are_auto_scheduled():
    assert classify_source("gs://raw/control/urls.tsv", 1) is None
    special = classify_source("gs://raw/x/raw/2026-07-17/recovered.jsonl.zst", 1)
    assert special is not None and special.kind == "nonstandard_raw"
