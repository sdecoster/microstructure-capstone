"""Real-data integration test for raw event-table construction and deduplication."""

from pathlib import Path

import pytest

from raw_tables import build_raw_event_tables


RAW_PATHS = (
    Path("data/raw_sample/raw/2026-08-16/1500.jsonl.zst"),
    Path("data/exploration_sample/raw/2026-08-16/1500.jsonl.zst"),
)


def _raw_path() -> Path:
    path = next((candidate for candidate in RAW_PATHS if candidate.exists()), None)
    if path is None:
        pytest.skip("Real raw sample is not available locally")
    return path


def test_real_raw_duplicates_are_removed_before_dataframe_expansion():
    tables = build_raw_event_tables(
        _raw_path(), max_messages=2_500, max_total_rows=20_000, show_progress=False
    )
    stats = tables["stats"]

    assert stats["outer_message_types"] == {"feed_message": 2_500}
    assert stats["duplicate_raw_events_skipped"] > 0
    assert stats["unique_raw_events"] + stats["duplicate_raw_events_skipped"] == 2_500
    assert not tables["price_changes"].empty
    assert "change_hash" not in tables["price_changes"].columns
    assert "book_hash" in tables["book_levels"].columns
    assert "transaction_hash" in tables["trades"].columns
