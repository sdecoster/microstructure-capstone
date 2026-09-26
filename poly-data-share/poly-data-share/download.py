#!/usr/bin/env python3
"""Download an R2 snapshot from the signed URLs in manifest.tsv."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import threading
import time
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the shared poly-raw snapshot with resume and retries."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("manifest.tsv"),
        help="TSV manifest path (default: manifest.tsv beside this script)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("poly-raw-2026-05-23-to-2026-08-16"),
        help="Destination directory",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=8,
        help="Concurrent downloads (default: 8)",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> list[tuple[int, Path, str]]:
    entries: list[tuple[int, Path, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            fields = line.rstrip("\n").split("\t", 2)
            if len(fields) != 3:
                raise ValueError(f"Invalid manifest row {line_number}")
            size_text, remote_path, url = fields
            pure_path = PurePosixPath(remote_path)
            if pure_path.is_absolute() or ".." in pure_path.parts:
                raise ValueError(f"Unsafe path on manifest row {line_number}")
            entries.append((int(size_text), Path(*pure_path.parts), url))
    return entries


def download_one(
    entry: tuple[int, Path, str], output: Path, attempts: int = 5
) -> tuple[str, int]:
    expected_size, relative_path, url = entry
    destination = output / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and destination.stat().st_size == expected_size:
        return ("skipped", expected_size)

    partial = destination.with_name(destination.name + ".part")
    for attempt in range(1, attempts + 1):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > expected_size:
                partial.unlink()
                offset = 0

            headers = {"User-Agent": "poly-raw-share-downloader/1.0"}
            if offset:
                headers["Range"] = f"bytes={offset}-"

            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                status = getattr(response, "status", response.getcode())
                append = offset > 0 and status == 206
                mode = "ab" if append else "wb"
                with partial.open(mode) as target:
                    shutil.copyfileobj(response, target, length=8 * 1024 * 1024)

            actual_size = partial.stat().st_size
            if actual_size != expected_size:
                raise IOError(
                    f"size mismatch for {relative_path}: "
                    f"expected {expected_size}, got {actual_size}"
                )
            os.replace(partial, destination)
            return ("downloaded", expected_size)
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(min(2**attempt, 30))

    raise RuntimeError("unreachable")


def main() -> int:
    args = parse_args()
    if args.jobs < 1:
        raise ValueError("--jobs must be at least 1")

    entries = load_manifest(args.manifest)
    total_bytes = sum(size for size, _, _ in entries)
    args.output.mkdir(parents=True, exist_ok=True)
    print(
        f"Downloading {len(entries):,} objects "
        f"({total_bytes / 1024**4:.3f} TiB) to {args.output}"
    )

    lock = threading.Lock()
    completed = 0
    failed: list[tuple[Path, str]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        future_to_entry = {
            pool.submit(download_one, entry, args.output): entry for entry in entries
        }
        for future in concurrent.futures.as_completed(future_to_entry):
            _, relative_path, _ = future_to_entry[future]
            try:
                future.result()
            except Exception as exc:
                failed.append((relative_path, str(exc)))
                print(f"FAILED: {relative_path}: {exc}", file=sys.stderr)
            with lock:
                completed += 1
                if completed % 10 == 0 or completed == len(entries):
                    print(f"Progress: {completed:,}/{len(entries):,}", flush=True)

    if failed:
        print(
            f"{len(failed)} object(s) failed. Re-run the same command to resume.",
            file=sys.stderr,
        )
        return 1

    print("Download complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
