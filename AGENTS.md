# Working agreement for AI contributors

## Purpose

This repository explores Polymarket raw feed data. It favors bounded, auditable transformations over broad downloads or implicit assumptions about archive completeness.

## First reading

Read `README.md`, then `raw_tables.py` and `order_book.py`. For the current research conclusion, read `market_filtering_assessment.md`. Treat `investigation/market_filtering_initial_assessment.md` as superseded context; the root assessment is the current recommendation.

## Data and safety rules

- Never commit `data/`, raw `.jsonl.zst` files, API-response caches, credentials, or `.env` files.
- Do not claim missing raw observations mean zero market activity.
- Do not silently backfill a missing opening book with a later snapshot.
- Preserve exact market/asset identifiers; a recurring market family is not one continuous contract.
- Keep raw values lossless where order-book arithmetic is involved. The reconstruction module intentionally uses `Decimal`.
- Keep scans bounded by message/row caps and reuse local caches rather than re-downloading data without need.

## Code expectations

- Make the smallest focused change and add or update tests in `tests/`.
- Run `py -m pytest -q tests` after Python changes. Some tests skip when ignored local real-data cache is unavailable.
- Document changes to data assumptions, filter rules, or evidence in the appropriate Markdown report.
- Avoid editing saved `investigation/results/` evidence unless regenerating it deliberately and explaining provenance.

## Key interfaces

`build_raw_event_tables()` accepts one or more raw Zstandard JSONL paths and returns normalized price-change, trade, and snapshot-level tables plus quality statistics. `reconstruct_book()` applies asset-specific deltas after a snapshot; its output is a `BookState` with normalized book levels and provenance times.
