# Cloud processing handoff

## Current objective

Convert the transferred Polymarket raw archive into a compact, auditable Parquet archive that can later be filtered by market.  Do **not** rescan raw data per market.  Process each source object once, in parallel, then use market-addressable partitions/dimensions.

## Google Cloud state

- Project: `polymarket-capstone`
- Raw bucket: `gs://poly-capstone-raw`
- Compact bucket: `gs://poly-capstone-compact`
- Both buckets and the worker VM are in `us-east`.
- VM: `poly-archive-worker`, zone `us-east1-c`, `e2-standard-8`, 200 GB balanced disk.
- Service account: `poly-archive-worker@polymarket-capstone.iam.gserviceaccount.com`.
- IAM: raw bucket Object Viewer; compact bucket Object Viewer + Object Creator.
- The complete ~3.013 TB archive has already transferred successfully.  Do not retransfer it and do not delete raw objects.
- The VM has a Python virtual environment at `~/poly-archive/.venv` with `pyarrow`, `zstandard`, and `google-cloud-storage` installed.

## Raw-object layout

Transferred raw object paths are under:

`gs://poly-capstone-raw/preserved/0438b0973b157d99ab8d5bd9f35d28a1.r2.cloudflarestorage.com/poly-raw/raw/...`

The ordinary hour pattern is `raw/YYYY-MM-DD/HHMM.jsonl.zst`.  There are 1,691 ordinary hourly objects totaling **2,906,585,311,256 bytes** according to the current real-manifest planner test.  Nonstandard/recovered raw objects exist and must be retained/audited separately, not silently scheduled as ordinary hours.

## Successful real cloud pilot

Input object:

`gs://poly-capstone-raw/preserved/0438b0973b157d99ab8d5bd9f35d28a1.r2.cloudflarestorage.com/poly-raw/raw/2026-08-16/0900.jsonl.zst`

Input compressed size: **402,143,244 bytes** (383.51 MiB).

The VM successfully streamed and converted the entire object in **272.398 seconds**.  The completed output was uploaded under:

`gs://poly-capstone-compact/pilot/pilot-20260816-0900-v3/`

Pilot facts:

- 7,545,435 outer messages.
- 3,699,947 exact duplicate feed payloads skipped within the source object (~49.1%).  This confirms duplicates originate in the received feed; do not use a post-hoc DataFrame `drop_duplicates()` as the primary remedy.
- 662 invalid-content envelopes and 5,191 non-feed envelopes.  Production must preserve audit records/counts for these rather than silently losing them.
- Event types: 3,754,374 `price_change`, 57,152 `book`, 27,879 `last_trade_price`, and **230 `tick_size_change`**.  The pilot only counted `tick_size_change`; production must preserve it.
- 6,593 markets and 13,186 assets: exactly two assets per market in this full hour.
- Fact rows: 7,508,748 price changes, 57,152 book headers, 4,705,148 book levels, 27,879 trades.
- Parquet fact bytes: 78,828,016, about 19.6% of compressed raw input, excluding small dimension files.  This is a pilot layout, not the final sharded layout.
- Single-worker compressed-input rate: about 1.47 MB/s.  At that rate, 2.907 TB is ~22.9 days.  CPU time (267.4 sec) nearly equaled wall time (272.4 sec), so CPU-bound parallel processing should help.  Start with four workers, not eight.

## Existing repository rules

Read `AGENTS.md`, `README.md`, `raw_tables.py`, `order_book.py`, and `market_filtering_assessment.md` first.  Important rules:

- No synthetic data in tests; use cached real data and skip if unavailable.
- Never treat missing raw observations as zero activity or backfill a missing opening book.
- Preserve contract boundaries and exact IDs in dimensions.
- Use exact scaled integers or Decimal-safe conversion for order-book numeric values.
- Never commit `data/`, credentials, signed URLs, or raw captures.
- Run `py -m pytest -q tests` after edits.

## Git state

Remote: `https://github.com/sdecoster/microstructure-capstone.git`

Branch already pushed: `cloud-pipeline`.

Commits on it:

- `dde5055` ? cloud archive transfer setup and real-manifest test.
- `b75b6f2` / `5e58331` ? `investigation/cloud_parallel_plan.py` and real-manifest tests.

The branch currently has a **planner only**, not a runnable converter.  It lists GCS object metadata, classifies ordinary vs nonstandard raw objects, and byte-balances ordinary objects across workers.  It is intentionally not sufficient to launch full processing.  At last check the suite passed: **16 passed**.

## Required implementation

Implement and push a real runnable converter before asking the user to do anything else.

1. Use `google.cloud.storage.Blob.open("rb")` + `zstandard` streaming.  Do not stage all raw data locally and do not load an hour?s fact rows into memory at once.
2. Run four independent processes, each with distinct assigned source objects.  No object may be read by more than one worker.
3. Create unique output paths and a per-source completion manifest/checkpoint; restart should skip only sources whose completion manifest validates.
4. Deduplicate exact payloads only **within the source object**.  Do not deduplicate across different source/recovery objects without an explicit audit design.
5. Store separate facts: `price_changes`, `trades`, `book_headers`, `book_levels`, `tick_size_changes`, plus `other_feed_events` and `non_feed_envelopes`/invalid-content audit tables.
6. Drop ingest time and repeated change hashes.  Retain transaction hashes with trades and snapshot hash once in `book_headers`.
7. Use integer price/size scaling at 1e6 only after rejecting excess nonzero precision.  Record scale in metadata.
8. Use deterministic stable keys (e.g. 128-bit BLAKE2b) for market and asset IDs so workers need no shared mutable SQLite DB.  Store original IDs once in dimensions and add a collision audit.
9. Prefer final paths conceptually like `table=price_changes/date=YYYY-MM-DD/market_shard=NN/source=<hash>/part-*.parquet`.  Do not create one tiny file per market-day.  A later compaction phase can merge source parts within date/shard.
10. Upload each completed source?s output to the compact bucket, verify the remote completion manifest, then remove only that source?s local temporary staging.  Never delete raw data.
11. Run a second full real-hour pilot using the GitHub code before launching all ordinary hours.  Validate row counts, event-type accounting, dimensions, duplicate rate, output bytes, and the presence of the 230 tick-size events.

## User preference / interaction constraint

The user is frustrated by repeated pasted commands and status-only messages.  Work autonomously.  Do not tell them what you intend to do and stop.  Do not ask them to paste large scripts.  Put code on the `cloud-pipeline` branch, push it, test it, then provide only the minimal VM `git pull` and launch command when it is genuinely runnable.
