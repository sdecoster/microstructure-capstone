"""Reconstruct an asset's limit order book from raw snapshot and delta tables."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class BookState:
    """A reconstructed book at one instant, with exact Decimal price/size values."""

    levels: pd.DataFrame
    snapshot_time: pd.Timestamp
    as_of: pd.Timestamp
    updates_applied: int


def _utc_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _decimal(value: Any, column: str) -> Decimal:
    if pd.isna(value):
        raise ValueError(f"Missing {column} in order-book data")
    return Decimal(str(value))


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{name} is missing required columns: {sorted(missing)}")


def _filter_asset(
    frame: pd.DataFrame, market_id: str, asset_id: str
) -> pd.DataFrame:
    return frame.loc[
        frame["market_id"].astype(str).eq(str(market_id))
        & frame["asset_id"].astype(str).eq(str(asset_id))
    ].copy()


def _levels_from_snapshot(snapshot: pd.DataFrame) -> tuple[dict[Decimal, Decimal], dict[Decimal, Decimal]]:
    bids: dict[Decimal, Decimal] = {}
    asks: dict[Decimal, Decimal] = {}

    for row in snapshot.itertuples(index=False):
        side = str(row.side).upper()
        price = _decimal(row.price, "price")
        size = _decimal(row.size, "size")

        if size < 0:
            raise ValueError("Snapshot contains a negative size")
        if side == "BID":
            bids[price] = size
        elif side == "ASK":
            asks[price] = size
        else:
            raise ValueError(f"Unknown snapshot side: {side!r}")

    return bids, asks


def _frame_from_levels(
    bids: dict[Decimal, Decimal],
    asks: dict[Decimal, Decimal],
    market_id: str,
    asset_id: str,
) -> pd.DataFrame:
    rows = [
        {"market_id": market_id, "asset_id": asset_id, "side": "BID", "price": price, "size": size}
        for price, size in sorted(bids.items(), reverse=True)
        if size > 0
    ]
    rows.extend(
        {"market_id": market_id, "asset_id": asset_id, "side": "ASK", "price": price, "size": size}
        for price, size in sorted(asks.items())
        if size > 0
    )
    return pd.DataFrame(rows, columns=["market_id", "asset_id", "side", "price", "size"])


def snapshot_book(
    book_levels: pd.DataFrame,
    market_id: str,
    asset_id: str,
    snapshot_time: Any,
) -> pd.DataFrame:
    """Return one exact raw book snapshot as a normalized BID/ASK DataFrame."""
    _require_columns(book_levels, {"market_id", "asset_id", "event_time", "side", "price", "size"}, "book_levels")
    target_time = _utc_timestamp(snapshot_time)
    asset_books = _filter_asset(book_levels, market_id, asset_id)
    asset_books["event_time"] = pd.to_datetime(asset_books["event_time"], utc=True)
    snapshot = asset_books.loc[asset_books["event_time"].eq(target_time)]

    if snapshot.empty:
        raise ValueError("No book snapshot exists for this market, asset, and timestamp")

    bids, asks = _levels_from_snapshot(snapshot)
    return _frame_from_levels(bids, asks, str(market_id), str(asset_id))


def reconstruct_book(
    book_levels: pd.DataFrame,
    price_changes: pd.DataFrame,
    market_id: str,
    asset_id: str,
    as_of: Any,
    *,
    snapshot_time: Any | None = None,
) -> BookState:
    """
    Rebuild an asset book at ``as_of`` from a raw snapshot and subsequent deltas.

    ``BUY`` price changes update bids; ``SELL`` price changes update asks. A size
    of zero removes that price level. If ``snapshot_time`` is omitted, the latest
    snapshot at or before ``as_of`` is used.
    """
    _require_columns(book_levels, {"market_id", "asset_id", "event_time", "side", "price", "size"}, "book_levels")
    _require_columns(price_changes, {"market_id", "asset_id", "event_time", "side", "price", "size"}, "price_changes")

    as_of_time = _utc_timestamp(as_of)
    asset_books = _filter_asset(book_levels, market_id, asset_id)
    asset_books["event_time"] = pd.to_datetime(asset_books["event_time"], utc=True)

    available_times = asset_books.loc[
        asset_books["event_time"].le(as_of_time), "event_time"
    ].drop_duplicates()
    if available_times.empty:
        raise ValueError("No snapshot exists at or before the requested time")

    base_time = (
        _utc_timestamp(snapshot_time)
        if snapshot_time is not None
        else available_times.max()
    )
    if base_time > as_of_time:
        raise ValueError("snapshot_time must be at or before as_of")

    base = snapshot_book(asset_books, market_id, asset_id, base_time)
    bids = {row.price: row.size for row in base.loc[base["side"].eq("BID")].itertuples(index=False)}
    asks = {row.price: row.size for row in base.loc[base["side"].eq("ASK")].itertuples(index=False)}

    updates = _filter_asset(price_changes, market_id, asset_id)
    updates["event_time"] = pd.to_datetime(updates["event_time"], utc=True)
    updates = updates.loc[
        updates["event_time"].gt(base_time) & updates["event_time"].le(as_of_time)
    ].sort_values("event_time", kind="stable")

    for row in updates.itertuples(index=False):
        side = str(row.side).upper()
        levels = bids if side == "BUY" else asks if side == "SELL" else None
        if levels is None:
            raise ValueError(f"Unknown price-change side: {side!r}")

        price = _decimal(row.price, "price")
        size = _decimal(row.size, "size")
        if size < 0:
            raise ValueError("Price change contains a negative size")
        if size == 0:
            levels.pop(price, None)
        else:
            levels[price] = size

    return BookState(
        levels=_frame_from_levels(bids, asks, str(market_id), str(asset_id)),
        snapshot_time=base_time,
        as_of=as_of_time,
        updates_applied=len(updates),
    )


def books_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """Compare two normalized books using exact Decimal price and size values."""
    required = {"side", "price", "size"}
    _require_columns(left, required, "left book")
    _require_columns(right, required, "right book")

    def normalized(frame: pd.DataFrame) -> list[tuple[str, Decimal, Decimal]]:
        return sorted(
            (str(row.side).upper(), _decimal(row.price, "price"), _decimal(row.size, "size"))
            for row in frame.loc[:, ["side", "price", "size"]].itertuples(index=False)
        )

    return normalized(left) == normalized(right)


def plot_order_book(
    book: BookState | pd.DataFrame,
    *,
    ax: Any | None = None,
    title: str | None = None,
):
    """Draw bid and ask liquidity at one reconstructed-book instant.

    Pass either the ``BookState`` returned by :func:`reconstruct_book` or its
    ``levels`` DataFrame. The function returns the Matplotlib axes so callers
    can add annotations or save the figure.
    """
    import matplotlib.pyplot as plt

    levels = book.levels if isinstance(book, BookState) else book
    _require_columns(levels, {"side", "price", "size"}, "book")
    if levels.empty:
        raise ValueError("Cannot plot an empty order book")

    plot_data = levels.copy()
    plot_data["price"] = pd.to_numeric(plot_data["price"], errors="raise")
    plot_data["size"] = pd.to_numeric(plot_data["size"], errors="raise")
    bids = plot_data.loc[plot_data["side"].astype(str).str.upper().eq("BID")]
    asks = plot_data.loc[plot_data["side"].astype(str).str.upper().eq("ASK")]

    unique_prices = sorted(plot_data["price"].unique())
    if len(unique_prices) > 1:
        width = min(right - left for left, right in zip(unique_prices, unique_prices[1:])) * 0.8
    else:
        width = max(abs(unique_prices[0]) * 0.01, 0.001)

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 5))

    ax.bar(bids["price"], bids["size"], width=width, color="tab:green", alpha=0.7, label="Bids")
    ax.bar(asks["price"], asks["size"], width=width, color="tab:red", alpha=0.7, label="Asks")
    ax.set_xlabel("Price")
    ax.set_ylabel("Available size")
    ax.legend()

    if title is None and isinstance(book, BookState):
        title = f"Order book at {book.as_of} ({book.updates_applied:,} deltas applied)"
    if title:
        ax.set_title(title)

    return ax
