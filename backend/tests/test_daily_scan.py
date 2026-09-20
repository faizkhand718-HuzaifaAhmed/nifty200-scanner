import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.services.daily_scan import build_nifty_daily_frame, compute_daily_scan_row  # noqa: E402
from app.market_data.exceptions import ProviderAPIError  # noqa: E402


@dataclass
class FakeCandle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


def make_daily_candles(n: int, start_price: float = 100.0, daily_drift: float = 0.3) -> List[FakeCandle]:
    candles = []
    base = date(2025, 1, 2)
    price = start_price
    for i in range(n):
        d = base + timedelta(days=i)
        ts = datetime(d.year, d.month, d.day, 9, 15, tzinfo=timezone.utc)
        price += daily_drift
        candles.append(FakeCandle(timestamp=ts, open=price - 0.5, high=price + 1.0, low=price - 1.0, close=price, volume=100000 + i * 10))
    return candles


class FakeProvider:
    def __init__(self, candles_by_symbol):
        self.candles_by_symbol = candles_by_symbol
        self.calls = []

    def get_historical_candles(self, symbol, exchange, timeframe, start, end):
        self.calls.append(symbol)
        if symbol not in self.candles_by_symbol:
            raise ProviderAPIError(f"no data for {symbol}")
        return self.candles_by_symbol[symbol]


def test_compute_daily_scan_row_produces_a_full_result_with_enough_history():
    candles = make_daily_candles(300)
    provider = FakeProvider({"RELIANCE": candles})

    row = compute_daily_scan_row("RELIANCE", provider)

    assert row.error is None
    assert row.symbol == "RELIANCE"
    assert row.price == pytest.approx(candles[-1].close)
    assert row.ema_20 is not None
    assert row.ema_50 is not None
    assert row.ema_200 is not None
    assert row.rsi is not None
    assert row.pct_from_52w_high is not None
    assert row.setup_score.total_score >= 0


def test_compute_daily_scan_row_change_pct_hand_computed():
    candles = make_daily_candles(300)
    provider = FakeProvider({"RELIANCE": candles})
    row = compute_daily_scan_row("RELIANCE", provider)

    expected = (candles[-1].close - candles[-2].close) / candles[-2].close * 100
    assert row.change_pct == pytest.approx(expected)


def test_compute_daily_scan_row_handles_provider_failure_gracefully():
    provider = FakeProvider({})
    row = compute_daily_scan_row("RELIANCE", provider)

    assert row.error is not None
    assert "RELIANCE" in row.error
    assert row.ema_20 is None
    assert row.setup_score.total_score == pytest.approx(0.0)


def test_compute_daily_scan_row_insufficient_history_gives_none_not_fabricated_values():
    candles = make_daily_candles(50)
    provider = FakeProvider({"RELIANCE": candles})
    row = compute_daily_scan_row("RELIANCE", provider)

    assert row.error is None
    assert row.ema_200 is None
    assert row.pct_from_52w_high is None
    assert "breakout_52week" in row.setup_score.unavailable_categories


def test_build_nifty_daily_frame_returns_none_on_failure_not_a_crash():
    provider = FakeProvider({})
    frame = build_nifty_daily_frame(provider)
    assert frame is None


def test_build_nifty_daily_frame_used_for_relative_strength():
    stock_candles = make_daily_candles(300, start_price=100.0, daily_drift=0.5)
    nifty_candles = make_daily_candles(300, start_price=20000.0, daily_drift=1.0)
    provider = FakeProvider({"RELIANCE": stock_candles, "NIFTY 50": nifty_candles})

    nifty_frame = build_nifty_daily_frame(provider)
    assert nifty_frame is not None

    row = compute_daily_scan_row("RELIANCE", provider, nifty_frame=nifty_frame)
    relative_strength_category = next(c for c in row.setup_score.categories if c.name == "relative_strength")
    assert relative_strength_category.available is True


def test_nifty_frame_fetched_once_not_per_symbol():
    stock_candles = make_daily_candles(300)
    nifty_candles = make_daily_candles(300, start_price=20000.0)
    provider = FakeProvider({"RELIANCE": stock_candles, "TCS": stock_candles, "NIFTY 50": nifty_candles})

    nifty_frame = build_nifty_daily_frame(provider)
    assert provider.calls == ["NIFTY 50"]

    compute_daily_scan_row("RELIANCE", provider, nifty_frame=nifty_frame)
    compute_daily_scan_row("TCS", provider, nifty_frame=nifty_frame)
    assert provider.calls.count("NIFTY 50") == 1
