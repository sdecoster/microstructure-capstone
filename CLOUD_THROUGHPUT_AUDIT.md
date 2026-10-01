# Cloud throughput audit — 2026-10-01

The running job is not using the eight available vCPUs effectively. Scaling the old code linearly from CPU count is not a sound forecast. The most important new finding is a per-record cross-process shutdown check introduced after the original single-source timing.

## Live observations

Read-only `vmstat` and `pidstat` samples from `poly-archive-worker-1` showed 56–57% idle CPU and essentially zero disk I/O wait. The four conversion processes each used about 52–53% of one CPU; their Manager coordinator used about 118% by itself. Each converter performed about 4,000 voluntary context switches per second. The system-wide context-switch rate exceeded 100,000/s during one sample. Staging occupied 2.3 GB, so local disk capacity was not the observed bottleneck.

`convert()` receives a `Manager.Event` in production. The old inner loop calls `is_set()` once for every raw record, including duplicates. That is an interprocess request/response, not a cheap local flag read. The single-source `--pilot-source` path passes no event, so the original pilot did not measure this overhead. This is a concrete explanation for why the pilot-based estimate missed the production behavior; its exact whole-run contribution still needs a production-path pilot.

Three existing May 31 logs show uploads taking 140.2, 153.4, and 177.2 seconds after 25,073.4, 27,044.1, and 29,368.3 seconds of conversion, respectively. Upload time was about 0.6% of total elapsed time. Two completion manifests contained 2,294 and 2,389 files, each about 1.33 GB in aggregate. File-count reduction is useful for operations and queries, but parallel upload is not the main current speed lever.

## Bounded local experiment

`investigation/cloud_hotpath_audit.py` replays real cached May 25 08:00 and August 14 09:00 prefixes through deployed/current transformation functions and the actual Parquet writer. Four processes each handle 50,000 records. The script compares shutdown polling frequency separately from prepared parsing/numeric improvements and duplicate detection before inner JSON decoding. It repeats all modes after warm-up. It reads no cloud data and deletes its temporary Parquet output after hashing it.

Warmed second cycle, aggregate wall time including output hashing and temporary-file cleanup:

| Variant | Seconds | Speed relative to deployed |
|---|---:|---:|
| Deployed transformations, shutdown RPC every record | 16.32 | 1.00x |
| Same transformations, shutdown RPC every 1,024 records | 5.55 | 2.94x |
| Prepared numeric/hash caching, same reduced polling | 4.51 | 3.62x |
| Also reject known duplicate strings before decoding their JSON | 4.05 | 4.03x |

Every variant produced byte-identical Parquet files on both samples. All row counts, unique-payload counts, and duplicate counts matched. The local environment used Python 3.9 and standard-library JSON (orjson was not installed); the prepared cloud runtime includes orjson. These are bounded prefix measurements on Windows with small deduplication sets. They do not establish fourfold end-to-end speedup on Linux, mature per-hour deduplication sets, or GCS. Raw measured aggregates are retained in ignored `data/cloud_hotpath_audit_20261001_repeat.json`.

Reproduce: `py investigation/cloud_hotpath_audit.py --cap 50000 --processes 4 --output data/cloud_hotpath_audit_repeat.json`.

## Prepared changes

- Keep immediate stop checks at source boundaries and uploads, but check the Manager event every 1,024 input records in the read loop. A cancellation can process up to that many additional records before being observed; blocking network calls retain their existing timeout behavior.
- For raw string payloads already known to be valid, recognize an exact duplicate before inner JSON parsing. Invalid payloads are still audited individually; deduplication remains within one source.
- Add `--max-sources` to cap the normal production process-pool path. The next cloud pilot must use this path, because the single-source pilot omitted the very coordination overhead that caused trouble.

The running VM has not been restarted or updated with these changes. The cloud pilot remains subject to the user's go-ahead.

## Assumptions we can change deliberately

The exact ordinary-source manifest splits into 290 pre-June-18 sources totaling 1,892,471,485,132 bytes and 1,401 June-18-onward sources totaling 1,014,113,826,124 bytes. The primary development window recommended in `market_filtering_assessment.md` is therefore only 34.9% of ordinary source bytes. Prioritizing that window gives an earlier research deliverable; finishing every date still requires the remaining work. Reverse chronological scheduling is already prepared but is not in the old running process.

The current objective converts all markets. If the actual first deliverable is the recommended eight rolling crypto series, saved bounded estimates suggest about 50.8 GB of compact post-June-18 data versus 233.1 GB for all markets. Those are sample-based storage estimates, not production measurements or proportional CPU savings. Early filtering can avoid row construction, numeric conversion, buffering, and writing for unrelated markets, but still requires reading/decompressing the mixed raw stream and sufficiently reliable identity metadata. Unknown labels cannot silently mean irrelevant markets. Such a scope change needs an explicit choice.

Do not discard snapshots, depth updates, exact identifiers, or numeric precision merely for speed: these support the intended book reconstruction. Retain raw data for audit and later alternatives. Sampling every Nth update or limiting deduplication to adjacent messages changes the dataset and is not a transparent optimization.

## Further candidates, ranked after the measured fix

1. Bound total buffered rows across shards. The current 50,000-row limit applies separately to each of 64 shards and each table; price changes alone can retain nearly 3.2 million row dictionaries per process. Lower memory use could permit more useful processes within the existing VM sizes. Combining smaller buffers with appendable Parquet row groups avoids multiplying tiny output objects. This requires fixed schemas and parity tests before rollout.
2. Avoid retaining full market/asset strings in every fact-row buffer once reversible dimensions exist; use compact keys and column-oriented buffers. This changes physical schema and therefore needs a versioned layout, not silent mixing with completed outputs.
3. Validate completed outputs via paginated metadata listings per source attempt instead of one metadata request per file, if restart validation becomes expensive. Preserve equivalent size/checksum validation.
4. Reconsider process count after coordination overhead is removed and RAM is measured on large sources. Eight vCPUs do not imply eight safe processes when each deduplication set spans tens of millions of unique messages.

No additional speed factor is assigned to these unmeasured candidates. The 34-day estimate describes the old running implementation; a replacement forecast should use a bounded concurrency pilot and then representative early- and late-period source measurements.
