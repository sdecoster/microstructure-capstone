"""Build tidy, bounded event tables from Polymarket raw .jsonl.zst files."""

from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import zstandard as zstd
from tqdm.auto import tqdm


PRICE_CHANGE_COLUMNS = [
    "market_id", "asset_id", "event_timestamp_ms", "price", "size", "side",
    "best_bid", "best_ask",
]
TRADE_COLUMNS = [
    "market_id", "asset_id", "event_timestamp_ms", "price", "size", "side",
    "fee_rate_bps", "transaction_hash",
]
BOOK_LEVEL_COLUMNS = [
    "market_id", "asset_id", "event_timestamp_ms", "book_hash", "side",
    "price", "size",
]


class _ProgressReader(io.RawIOBase):
    """Expose compressed bytes consumed to tqdm while zstandard reads a file."""

    def __init__(self, raw, progress_bar, on_read=None) -> None:
        self.raw = raw
        self.progress_bar = progress_bar
        self.on_read = on_read

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        count = self.raw.readinto(buffer)
        if count:
            self.progress_bar.update(count)
            if self.on_read is not None:
                self.on_read(count)
        return count


def _parse_content(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def _scalar_market_id(content: dict[str, Any]) -> str | int | None:
    value = content.get("market")
    return value if isinstance(value, (str, int)) else None


def _event_fingerprint(content: dict[str, Any]) -> bytes:
    """Hash the actual feed payload, deliberately excluding outer ingest time."""
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.blake2b(canonical.encode("utf-8"), digest_size=16).digest()


def _as_table(
    rows: list[dict[str, Any]], columns: list[str], numeric_columns: tuple[str, ...]
) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return frame.drop(columns="event_timestamp_ms").assign(
            event_time=pd.Series(dtype="datetime64[ns, UTC]")
        )

    timestamp_ms = pd.to_numeric(frame.pop("event_timestamp_ms"), errors="coerce")
    frame["event_time"] = pd.to_datetime(
        timestamp_ms, unit="ms", utc=True, errors="coerce"
    )
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    return frame.sort_values(
        ["market_id", "asset_id", "event_time"], kind="stable"
    ).reset_index(drop=True)


def _raw_paths(paths: str | Path | Iterable[str | Path]) -> list[Path]:
    if isinstance(paths, (str, Path)):
        paths = [paths]
    normalized = [Path(path) for path in paths]
    if not normalized:
        raise ValueError("At least one raw .jsonl.zst path is required")
    for path in normalized:
        if not path.is_file():
            raise FileNotFoundError(path)
    return normalized


def build_raw_event_tables(
    paths: str | Path | Iterable[str | Path],
    *,
    max_messages: int = 50_000,
    max_total_rows: int = 200_000,
    deduplicate_events: bool = True,
    show_progress: bool = True,
) -> dict[str, Any]:
    """
    Convert bounded raw data into separate price-change, trade, and book-level tables.

    ``max_messages`` limits raw outer records read across all supplied files and
    ``max_total_rows`` limits rows emitted across all three tables. Exact repeated
    raw feed payloads are removed *before* they expand into DataFrame rows.
    Storage policy: discard per-change hashes from output, but keep snapshot
    and transaction hashes. Deduplication still fingerprints the FULL payload,
    including source hashes, before selecting output columns.
    """
    if max_messages < 1 or max_total_rows < 1:
        raise ValueError("max_messages and max_total_rows must both be positive")

    raw_paths = _raw_paths(paths)
    price_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    book_rows: list[dict[str, Any]] = []
    seen_fingerprints: set[bytes] = set()

    stats: dict[str, Any] = {
        "files": [str(path) for path in raw_paths],
        "outer_messages_read": 0,
        "compressed_bytes_read": 0,
        "unique_raw_events": 0,
        "duplicate_raw_events_skipped": 0,
        "invalid_content_messages": 0,
        "outer_message_types": Counter(),
        "event_types": Counter(),
        "unknown_event_types": Counter(),
        "stopped_at_message_cap": False,
        "stopped_at_row_cap": False,
    }

    def emitted_rows() -> int:
        return len(price_rows) + len(trade_rows) + len(book_rows)

    stop = False
    for path in raw_paths:
        progress = tqdm(
            total=path.stat().st_size,
            unit="B",
            unit_scale=True,
            desc=f"Reading {path.name}",
            disable=not show_progress,
        )
        compressed = path.open("rb")
        tracked = _ProgressReader(
            compressed,
            progress,
            lambda count: stats.__setitem__(
                "compressed_bytes_read", stats["compressed_bytes_read"] + count
            ),
        )
        reader = zstd.ZstdDecompressor().stream_reader(tracked)
        source = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")

        try:
            for line in source:
                if not line.strip():
                    continue
                if stats["outer_messages_read"] >= max_messages:
                    stats["stopped_at_message_cap"] = True
                    stop = True
                    break

                outer = json.loads(line)
                stats["outer_messages_read"] += 1
                message_type = outer.get("message_type")
                stats["outer_message_types"][message_type] += 1
                if message_type != "feed_message":
                    raise ValueError(f"Unexpected outer message type: {message_type!r}")

                content = _parse_content(outer.get("content"))
                if not content:
                    stats["invalid_content_messages"] += 1
                    continue

                if deduplicate_events:
                    fingerprint = _event_fingerprint(content)
                    if fingerprint in seen_fingerprints:
                        stats["duplicate_raw_events_skipped"] += 1
                        continue
                    seen_fingerprints.add(fingerprint)

                stats["unique_raw_events"] += 1
                event_type = content.get("event_type")
                stats["event_types"][event_type] += 1
                market_id = _scalar_market_id(content)
                event_timestamp_ms = content.get("timestamp")

                if event_type == "price_change":
                    for change in content.get("price_changes", []):
                        if emitted_rows() >= max_total_rows:
                            stats["stopped_at_row_cap"] = True
                            stop = True
                            break
                        if not isinstance(change, dict):
                            continue
                        price_rows.append({
                            "market_id": market_id,
                            "asset_id": change.get("asset_id"),
                            "event_timestamp_ms": event_timestamp_ms,
                            "price": change.get("price"),
                            "size": change.get("size"),
                            "side": change.get("side"),
                            "best_bid": change.get("best_bid"),
                            "best_ask": change.get("best_ask"),
                        })

                elif event_type == "last_trade_price":
                    if emitted_rows() >= max_total_rows:
                        stats["stopped_at_row_cap"] = True
                        stop = True
                    else:
                        trade_rows.append({
                            "market_id": market_id,
                            "asset_id": content.get("asset_id"),
                            "event_timestamp_ms": event_timestamp_ms,
                            "price": content.get("price"),
                            "size": content.get("size"),
                            "side": content.get("side"),
                            "fee_rate_bps": content.get("fee_rate_bps"),
                            "transaction_hash": content.get("transaction_hash"),
                        })

                elif event_type == "book":
                    for raw_side, side in (("bids", "BID"), ("asks", "ASK")):
                        for level in content.get(raw_side, []):
                            if emitted_rows() >= max_total_rows:
                                stats["stopped_at_row_cap"] = True
                                stop = True
                                break
                            if isinstance(level, dict):
                                price, size = level.get("price"), level.get("size")
                            elif isinstance(level, (list, tuple)) and len(level) >= 2:
                                price, size = level[0], level[1]
                            else:
                                continue
                            book_rows.append({
                                "market_id": market_id,
                                "asset_id": content.get("asset_id"),
                                "event_timestamp_ms": event_timestamp_ms,
                                "book_hash": content.get("hash"),
                                "side": side,
                                "price": price,
                                "size": size,
                            })
                        if stop:
                            break

                else:
                    stats["unknown_event_types"][event_type] += 1

                if stop:
                    break
        finally:
            source.close()
            reader.close()
            compressed.close()
            progress.close()

        if stop:
            break

    price_changes = _as_table(
        price_rows, PRICE_CHANGE_COLUMNS,
        ("price", "size", "best_bid", "best_ask"),
    )
    trades = _as_table(trade_rows, TRADE_COLUMNS, ("price", "size", "fee_rate_bps"))
    book_levels = _as_table(book_rows, BOOK_LEVEL_COLUMNS, ("price", "size"))

    asset_map = pd.concat(
        [
            price_changes[["market_id", "asset_id"]],
            trades[["market_id", "asset_id"]],
            book_levels[["market_id", "asset_id"]],
        ],
        ignore_index=True,
    ).dropna().drop_duplicates().sort_values(["market_id", "asset_id"]).reset_index(drop=True)

    stats["outer_message_types"] = dict(stats["outer_message_types"])
    stats["event_types"] = dict(stats["event_types"])
    stats["unknown_event_types"] = dict(stats["unknown_event_types"])
    stats["rows"] = {
        "price_changes": len(price_changes),
        "trades": len(trades),
        "book_levels": len(book_levels),
    }

    return {
        "price_changes": price_changes,
        "trades": trades,
        "book_levels": book_levels,
        "asset_map": asset_map,
        "assets_per_market": asset_map.groupby("market_id")["asset_id"].nunique(),
        "stats": stats,
    }
