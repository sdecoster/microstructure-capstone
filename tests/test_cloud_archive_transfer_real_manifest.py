'''Validate the cloud-transfer planner against the supplied real manifest.'''
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'investigation'))
from cloud_archive_transfer import choose_pilot, read_manifest


def test_real_manifest_has_unique_transfer_destinations():
    rows = read_manifest()
    assert len(rows) == 6590
    assert sum(row.size for row in rows) == 3012570951236
    assert len({row.destination_object for row in rows}) == len(rows)


def test_real_pilot_is_bounded_and_spans_archive_areas():
    pilot = choose_pilot(read_manifest(), max_objects=3, max_bytes=75_000_000)
    assert 1 <= len(pilot) <= 3
    assert sum(row.size for row in pilot) <= 75_000_000
    assert all(row.source_path.startswith(('raw/', 'raw/_index/', 'raw/external/', 'raw/onchain/')) for row in pilot)
