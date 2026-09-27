"""Create auditable, byte-balanced source-object work plans for cloud conversion."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Iterable

REGULAR_RAW = re.compile(r"/raw/(\d{4}-\d{2}-\d{2})/(\d{4})\.jsonl\.zst$")

@dataclass(frozen=True)
class Source:
    uri: str
    size_bytes: int
    date: str | None
    hour: str | None
    kind: str

def classify_source(uri: str, size_bytes: int) -> Source | None:
    if size_bytes < 0 or not uri.startswith("gs://"):
        raise ValueError("Invalid cloud-storage object")
    if not uri.endswith(".jsonl.zst") or "/raw/" not in uri:
        return None
    match = REGULAR_RAW.search(uri)
    if match:
        return Source(uri, size_bytes, match.group(1), match.group(2), "regular_hour")
    return Source(uri, size_bytes, None, None, "nonstandard_raw")

def balance(sources: Iterable[Source], workers: int) -> list[list[Source]]:
    if workers < 1:
        raise ValueError("workers must be positive")
    bins = [[] for _ in range(workers)]
    totals = [0] * workers
    for source in sorted(sources, key=lambda row: (-row.size_bytes, row.uri)):
        target = min(range(workers), key=lambda index: (totals[index], index))
        bins[target].append(source)
        totals[target] += source.size_bytes
    for items in bins:
        items.sort(key=lambda row: (row.date or "", row.hour or "", row.uri))
    return bins

def build_plan(sources: Iterable[Source], workers: int) -> dict:
    sources = list(sources)
    regular = [source for source in sources if source.kind == "regular_hour"]
    special = [source for source in sources if source.kind != "regular_hour"]
    assignments = balance(regular, workers)
    return {
        "format_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": {"deduplication_scope": "within one source object only", "special_sources": "listed, never silently scheduled"},
        "regular_sources": len(regular),
        "regular_bytes": sum(source.size_bytes for source in regular),
        "nonstandard_sources": [asdict(source) for source in special],
        "workers": [{"worker": index, "bytes": sum(source.size_bytes for source in items), "sources": [asdict(source) for source in items]} for index, items in enumerate(assignments)],
    }

def list_sources(bucket: str) -> list[Source]:
    from google.cloud import storage
    result = []
    for blob in storage.Client().list_blobs(bucket):
        source = classify_source("gs://{}/{}".format(bucket, blob.name), blob.size or 0)
        if source is not None:
            result.append(source)
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-bucket", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = build_plan(list_sources(args.raw_bucket), args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    loads = [worker["bytes"] for worker in plan["workers"]]
    print(json.dumps({"regular_sources": plan["regular_sources"], "regular_bytes": plan["regular_bytes"], "nonstandard_sources": len(plan["nonstandard_sources"]), "min_worker_bytes": min(loads, default=0), "max_worker_bytes": max(loads, default=0)}, sort_keys=True))

if __name__ == "__main__":
    main()
