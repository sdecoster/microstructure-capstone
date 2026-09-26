"""Integration tests against the locally downloaded real Polymarket raw feed."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import pytest
import zstandard as zstd

from order_book import books_equal, plot_order_book, reconstruct_book, snapshot_book


RAW_PATHS = (
    Path("data/raw_sample/raw/2026-08-16/1500.jsonl.zst"),
    Path("data/exploration_sample/raw/2026-08-16/1500.jsonl.zst"),
)


def _raw_path() -> Path:
    path = next((candidate for candidate in RAW_PATHS if candidate.exists()), None)
    if path is None:
        pytest.skip("Real raw sample is not available locally")
    return path


def _book_rows(content: dict) -> list[dict]:
    rows = []
    for raw_side, side in (("bids", "BID"), ("asks", "ASK")):
        for level in content.get(raw_side, []):
            rows.append(
                {
                    "market_id": content["market"],
                    "asset_id": content["asset_id"],
                    "event_time": pd.to_datetime(int(content["timestamp"]), unit="ms", utc=True),
                    "side": side,
                    "price": level["price"],
                    "size": level["size"],
                }
            )
    return rows


def _price_change_rows(content: dict) -> list[dict]:
    event_time = pd.to_datetime(int(content["timestamp"]), unit="ms", utc=True)
    return [
        {
            "market_id": content["market"],
            "asset_id": change["asset_id"],
            "event_time": event_time,
            "side": change["side"],
            "price": change["price"],
            "size": change["size"],
        }
        for change in content["price_changes"]
    ]


def _find_real_reconciliation_case(path: Path):
    """Find two actual snapshots for one asset plus real deltas between them."""
    prior_snapshots: dict[tuple[str, str], dict] = {}
    deltas: dict[tuple[str, str], list[dict]] = {}

    with path.open("rb") as compressed:
        reader = zstd.ZstdDecompressor().stream_reader(compressed)
        source = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
        try:
            for line_number, line in enumerate(source, 1):
                outer = json.loads(line)
                content = json.loads(outer["content"])
                event_type = content.get("event_type")

                if event_type == "price_change":
                    for row in _price_change_rows(content):
                        key = (row["market_id"], row["asset_id"])
                        if key in prior_snapshots:
                            deltas[key].append(row)

                elif event_type == "book":
                    key = (content["market"], content["asset_id"])
                    if key in prior_snapshots and deltas[key]:
                        return prior_snapshots[key], deltas[key], content, line_number
                    prior_snapshots[key] = content
                    deltas[key] = []
        finally:
            source.close()

    pytest.fail("No two real book snapshots with intervening deltas were found")


def test_real_deltas_reconcile_to_next_snapshot():
    """Real delta application must reproduce the next real snapshot exactly."""
    first, deltas, second, line_number = _find_real_reconciliation_case(_raw_path())

    book_levels = pd.DataFrame(_book_rows(first) + _book_rows(second))
    price_changes = pd.DataFrame(deltas)
    market_id, asset_id = first["market"], first["asset_id"]
    first_time = pd.to_datetime(int(first["timestamp"]), unit="ms", utc=True)
    second_time = pd.to_datetime(int(second["timestamp"]), unit="ms", utc=True)

    rebuilt = reconstruct_book(
        book_levels,
        price_changes,
        market_id,
        asset_id,
        as_of=second_time,
        snapshot_time=first_time,
    )
    expected = snapshot_book(book_levels, market_id, asset_id, second_time)

    assert line_number > 0
    assert rebuilt.updates_applied == len(deltas)
    assert rebuilt.updates_applied > 0
    assert books_equal(rebuilt.levels, expected)


def test_real_latest_snapshot_is_selected_when_no_base_is_supplied():
    """At a real snapshot time, the default base is that exact latest snapshot."""
    first, deltas, second, _ = _find_real_reconciliation_case(_raw_path())
    book_levels = pd.DataFrame(_book_rows(first) + _book_rows(second))
    price_changes = pd.DataFrame(deltas)
    market_id, asset_id = first["market"], first["asset_id"]
    second_time = pd.to_datetime(int(second["timestamp"]), unit="ms", utc=True)

    rebuilt = reconstruct_book(
        book_levels,
        price_changes,
        market_id,
        asset_id,
        as_of=second_time,
    )
    expected = snapshot_book(book_levels, market_id, asset_id, second_time)

    assert rebuilt.snapshot_time == second_time
    assert rebuilt.updates_applied == 0
    assert books_equal(rebuilt.levels, expected)


def test_real_reconstructed_book_can_be_plotted():
    """The plotting helper accepts a BookState reconstructed from real feed data."""
    first, deltas, second, _ = _find_real_reconciliation_case(_raw_path())
    book_levels = pd.DataFrame(_book_rows(first) + _book_rows(second))
    price_changes = pd.DataFrame(deltas)
    second_time = pd.to_datetime(int(second["timestamp"]), unit="ms", utc=True)
    rebuilt = reconstruct_book(
        book_levels,
        price_changes,
        first["market"],
        first["asset_id"],
        as_of=second_time,
        snapshot_time=pd.to_datetime(int(first["timestamp"]), unit="ms", utc=True),
    )

    axes = plot_order_book(rebuilt)
    assert len(axes.patches) == len(rebuilt.levels)
