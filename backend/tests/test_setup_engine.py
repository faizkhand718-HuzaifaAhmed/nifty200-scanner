import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators.engine import IndicatorEngine  # noqa: E402
from app.market_data.calendar import NSECalendar  # noqa: E402
from app.market_data.enums import Timeframe  # noqa: E402
from app.setup_detection.config import SetupThresholds  # noqa: E402
from app.setup_detection.engine import SetupDetectionEngine  # noqa: E402

HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_calendar" / "nse_holidays_2026.json"
DAY1 = date(2026, 1, 27)
DAY2 = date(2026, 1, 28)
DAY3 = date(2026, 1, 29)


def build_ohlcv(days, minutes_step=15, seed_price=250.0) -> pd.DataFrame:
    calendar = NSECalendar.from_file(HOLIDAY_FILE)
    timestamps = []
    for d in days:
        timestamps.extend(calendar.session_timestamps(d, Timeframe(f"{minutes_step}m")))
    rows = []
    price = seed_price
    for i, ts in enumerate(timestamps):
        price += ((-1) ** i) * (0.3 + (i % 7) * 0.05)
        c = round(price, 2)
        rows.append((ts, c - 0.1, c + 0.4, c - 0.4, c, 500 + (i * 13) % 400))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


@pytest.fixture()
def stock_indicators():
    df = build_ohlcv([DAY1, DAY2, DAY3])
    return IndicatorEngine().compute(df)


@pytest.fixture()
def nifty_indicators():
    df = build_ohlcv([DAY1, DAY2, DAY3], seed_price=20000.0)
    return IndicatorEngine().compute(df)


def test_compute_produces_all_expected_columns(stock_indicators, nifty_indicators):
    result = SetupDetectionEngine().compute(stock_indicators, nifty_df=nifty_indicators)

    expected = {
        "long_above_vwap", "long_ema9_above_ema20", "long_ema20_above_ema50",
        "long_price_structure", "long_volume_confirmation", "long_relative_volume",
        "long_rsi", "long_adx_trend", "long_breakout", "long_retest", "long_market_confirmation",
        "short_below_vwap", "short_ema9_below_ema20", "short_ema20_below_ema50",
        "short_price_structure", "short_volume_confirmation", "short_relative_volume",
        "short_rsi", "short_adx_trend", "short_breakdown", "short_retest", "short_market_confirmation",
    }
    assert expected.issubset(set(result.columns))
    assert len(result) == len(stock_indicators)


def test_all_components_are_booleans_not_a_combined_verdict(stock_indicators, nifty_indicators):
    """Explicitly guards against the engine accidentally collapsing
    components into one pass/fail column - that's out of scope for this
    phase."""
    result = SetupDetectionEngine().compute(stock_indicators, nifty_df=nifty_indicators)
    component_cols = [c for c in result.columns if c.startswith("long_") or c.startswith("short_")]
    assert len(component_cols) >= 20
    assert "score" not in result.columns
    assert "verdict" not in result.columns
    for col in component_cols:
        non_null = result[col].dropna()
        assert non_null.isin([True, False]).all(), f"{col} contains a non-boolean value"


def test_market_confirmation_omitted_without_nifty_df(stock_indicators):
    result = SetupDetectionEngine().compute(stock_indicators, nifty_df=None)
    assert "long_market_confirmation" not in result.columns
    assert "short_market_confirmation" not in result.columns


def test_relative_strength_conditions_omitted_when_column_absent(stock_indicators, nifty_indicators):
    # stock_indicators was computed WITHOUT a nifty_df in IndicatorEngine,
    # so it has no 'relative_strength' column yet.
    assert "relative_strength" not in stock_indicators.columns
    result = SetupDetectionEngine().compute(stock_indicators, nifty_df=nifty_indicators)
    assert "long_relative_strength" not in result.columns
    assert "short_relative_strength" not in result.columns


def test_relative_strength_conditions_present_when_column_exists():
    stock_ohlcv = build_ohlcv([DAY1, DAY2, DAY3])
    nifty_ohlcv = build_ohlcv([DAY1, DAY2, DAY3], seed_price=20000.0)
    nifty_close_df = pd.DataFrame({"timestamp": nifty_ohlcv["timestamp"], "close": nifty_ohlcv["close"]})
    stock_with_rs = IndicatorEngine().compute(stock_ohlcv, nifty_df=nifty_close_df)
    assert "relative_strength" in stock_with_rs.columns

    nifty_full = IndicatorEngine().compute(nifty_ohlcv)
    result = SetupDetectionEngine().compute(stock_with_rs, nifty_df=nifty_full)
    assert "long_relative_strength" in result.columns
    assert "short_relative_strength" in result.columns


def test_missing_required_column_raises(stock_indicators):
    broken = stock_indicators.drop(columns=["vwap"])
    with pytest.raises(ValueError, match="missing required columns"):
        SetupDetectionEngine().compute(broken)


def test_latest_components_shape(stock_indicators, nifty_indicators):
    result = SetupDetectionEngine().compute(stock_indicators, nifty_df=nifty_indicators)
    latest = SetupDetectionEngine.latest_components(result)

    assert set(latest.keys()) == {"long", "short"}
    assert "above_vwap" in latest["long"]
    assert "below_vwap" in latest["short"]
    for v in latest["long"].values():
        assert isinstance(v, bool)
    for v in latest["short"].values():
        assert isinstance(v, bool)


def test_volume_conditions_identical_between_long_and_short(stock_indicators, nifty_indicators):
    """Volume/relative-volume aren't directional - documented, tested."""
    result = SetupDetectionEngine().compute(stock_indicators, nifty_df=nifty_indicators)
    assert (result["long_volume_confirmation"] == result["short_volume_confirmation"]).all()
    assert (result["long_relative_volume"] == result["short_relative_volume"]).all()


def test_custom_thresholds_are_respected(stock_indicators, nifty_indicators):
    strict = SetupThresholds(relative_volume_min=100.0)  # impossibly high bar
    result = SetupDetectionEngine(thresholds=strict).compute(stock_indicators, nifty_df=nifty_indicators)
    assert not result["long_relative_volume"].any()
    assert not result["short_relative_volume"].any()
