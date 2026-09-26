# Polymarket raw-data exploration

Utilities and evidence from an exploratory analysis of Polymarket event-feed archives. The core workflow reads compressed raw feed messages, produces tidy Pandas tables, and reconstructs an asset's limit order book from snapshots and subsequent price changes.

## Start here

```powershell
py -m pip install pandas zstandard tqdm matplotlib pytest
py -m pytest -q tests
```

The tests use locally cached real-data samples when available and skip dependent checks when they are not. Python 3.9+ is expected.

To turn one or more raw `.jsonl.zst` files into bounded tables:

```python
from raw_tables import build_raw_event_tables

tables = build_raw_event_tables(
    "data/raw_sample/raw/2026-08-16/1500.jsonl.zst",
    max_messages=50_000,
    max_total_rows=200_000,
)
print(tables["price_changes"].head())
```

`tables` contains `price_changes`, `trades`, `book_levels`, `asset_map`, `assets_per_market`, and read/quality `stats`. Use `order_book.reconstruct_book` to produce the book for a chosen market/asset at an instant; `plot_order_book` renders it.

## Repository map

- `raw_tables.py` — streaming Zstandard reader and event-table normalization.
- `order_book.py` — exact-Decimal snapshot/delta book reconstruction and plot.
- `explore_poly_data.ipynb` — exploratory notebook.
- `tests/` — tests against cached real observations.
- `investigation/` — bounded archive/API probes, evidence, and reports.
- `market_filtering_assessment.md` — current research recommendation and limits.
- `Papers/` — background paper and extracted text.

## Data policy

The raw archive cache is intentionally excluded from Git. It is about 4 GB in this working directory and includes compressed captures and API response caches. It is reproducible only where the underlying sources remain available; share it separately (for example, object storage with a manifest) if required. The repository retains code, reports, and small saved investigation results.

Do not put API keys, authenticated headers, or personal data into source files, notebooks, or committed data. Keep local configuration in an ignored `.env` file.

## Research cautions

The data is an observed recording, not a proven complete market history. Preserve contract boundaries, wait for an actual base snapshot before reconstructing a book, reset state over source gaps, and do not treat missing periods as zero activity. The assessment documents an observed collection-regime break and the recommended filters.

## Next work

The project is exploratory rather than packaged. Before turning it into a production pipeline, add pinned dependencies, explicit configuration, metadata versioning, and an incremental conversion/storage workflow.
