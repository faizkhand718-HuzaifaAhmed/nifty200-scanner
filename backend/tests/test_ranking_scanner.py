import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_data.calendar import NSECalendar  # noqa: E402
from app.market_data.enums import Timeframe  # noqa: E402
from app.market_data.providers.mock_provider import MockDataProvider  # noqa: E402
from app.ranking.engine import RankingEngine  # noqa: E402
from app.ranking.filters import RankingFilters, apply_filters, top_n  # noqa: E402
from app.ranking.scanner import scan_universe  # noqa: E402

HOLIDAY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_calendar" / "nse_holidays_2026.json"
IST = ZoneInfo("Asia/Kolkata")
SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]


@pytest.fixture()
def calendar():
    return NSECalendar.from_file(HOLIDAY_FILE)


@pytest.fixture()
def provider(calendar):
    p = MockDataProvider(calendar, seed=7)
    p.set_clock(datetime(2026, 1, 27, 12, 0, tzinfo=IST))  # mid-session, ordinary Tuesday
    return p


def test_scan_universe_produces_a_snapshot_per_symbol(provider, calendar):
    result = scan_universe(SYMBOLS, "NSE", provider, calendar, Timeframe.FIVE_MIN)
    assert len(result.snapshots) == len(SYMBOLS)
    assert result.skipped == {}


def test_scan_universe_skips_symbols_before_market_open(calendar):
    provider = MockDataProvider(calendar, seed=7)
    provider.set_clock(datetime(2026, 1, 27, 8, 0, tzinfo=IST))  # before 09:15 open
    result = scan_universe(SYMBOLS, "NSE", provider, calendar, Timeframe.FIVE_MIN)
    assert result.snapshots == []
    assert set(result.skipped.keys()) == set(SYMBOLS)


def test_full_pipeline_end_to_end_produces_ranked_table(provider, calendar):
    scan = scan_universe(SYMBOLS, "NSE", provider, calendar, Timeframe.FIVE_MIN)
    ranked = RankingEngine().rank(scan.snapshots)

    expected_columns = {
        "rank", "symbol", "price", "change_pct", "direction", "opportunity_score",
        "trend", "volume", "vwap", "rsi", "adx", "entry_status", "risk_reward", "setup_explanation",
    }
    assert expected_columns.issubset(set(ranked.columns))
    assert len(ranked) == len(SYMBOLS)
    assert list(ranked["rank"]) == list(range(1, len(SYMBOLS) + 1))
    # ranked descending by opportunity_score
    scores = list(ranked["opportunity_score"])
    assert scores == sorted(scores, reverse=True)


def test_top_n_variants(provider, calendar):
    scan = scan_universe(SYMBOLS, "NSE", provider, calendar, Timeframe.FIVE_MIN)
    ranked = RankingEngine().rank(scan.snapshots)

    assert len(top_n(ranked, 1)) == 1
    assert len(top_n(ranked, 3)) == 3
    assert len(top_n(ranked, 5)) == min(5, len(SYMBOLS))
    assert len(top_n(ranked, None)) == len(SYMBOLS)


def test_filters_apply_after_ranking(provider, calendar):
    scan = scan_universe(SYMBOLS, "NSE", provider, calendar, Timeframe.FIVE_MIN)
    ranked = RankingEngine().rank(scan.snapshots)

    long_only = apply_filters(ranked, RankingFilters(direction="LONG"))
    assert (long_only["direction"] == "LONG").all()

    high_score_only = apply_filters(ranked, RankingFilters(min_score=0.0))
    assert len(high_score_only) == len(ranked)  # every score is >= 0


def test_ranking_updates_automatically_with_new_data(calendar):
    """Re-running the scan at a different point in time (simulating new
    market data arriving) must produce a genuinely fresh ranking, not a
    cached/stale one - there is no persistent state in scan_universe or
    RankingEngine to go stale in the first place."""
    provider = MockDataProvider(calendar, seed=7)

    provider.set_clock(datetime(2026, 1, 27, 9, 45, tzinfo=IST))
    scan_early = scan_universe(SYMBOLS, "NSE", provider, calendar, Timeframe.FIVE_MIN)
    ranked_early = RankingEngine().rank(scan_early.snapshots)

    provider.set_clock(datetime(2026, 1, 27, 14, 30, tzinfo=IST))
    scan_later = scan_universe(SYMBOLS, "NSE", provider, calendar, Timeframe.FIVE_MIN)
    ranked_later = RankingEngine().rank(scan_later.snapshots)

    # More candles exist later in the day -> at least the prices (and
    # almost certainly the scores) differ from the earlier snapshot.
    early_prices = ranked_early.set_index("symbol")["price"]
    later_prices = ranked_later.set_index("symbol")["price"]
    assert not early_prices.equals(later_prices)


def test_one_failing_symbol_does_not_break_the_rest_of_the_scan(provider, calendar):
    """A single symbol's data/computation failure must be isolated - the
    rest of the universe should still be scanned and ranked."""

    class FlakyProvider:
        """Duck-typed wrapper: passes through to the real mock provider
        for every symbol except one, which always raises."""

        def __init__(self, inner, bad_symbol):
            self._inner = inner
            self._bad_symbol = bad_symbol

        def get_intraday_candles(self, symbol, *args, **kwargs):
            if symbol == self._bad_symbol:
                raise RuntimeError("simulated failure for this symbol only")
            return self._inner.get_intraday_candles(symbol, *args, **kwargs)

    flaky = FlakyProvider(provider, bad_symbol="TCS")
    result = scan_universe(SYMBOLS, "NSE", flaky, calendar, Timeframe.FIVE_MIN)

    assert "TCS" in result.skipped
    assert len(result.snapshots) == len(SYMBOLS) - 1
    assert {s.symbol for s in result.snapshots} == set(SYMBOLS) - {"TCS"}


def test_nifty_fetch_failure_degrades_gracefully_instead_of_crashing(provider, calendar):
    """If NIFTY's own data fetch fails (network issue, provider error),
    the scan must still succeed for every stock - just without Market
    Confirmation / Relative Strength - rather than the whole scan crashing
    because of one shared dependency."""
    from app.market_data.exceptions import ProviderAPIError

    provider.simulate_next_call_failure(ProviderAPIError("simulated NIFTY outage"))
    result = scan_universe(SYMBOLS, "NSE", provider, calendar, Timeframe.FIVE_MIN)

    assert len(result.snapshots) == len(SYMBOLS)
    assert result.skipped == {}
    # Market confirmation / relative strength must be absent, not fabricated.
    sample_setup_row = result.snapshots[0].setup_row
    assert "long_market_confirmation" not in sample_setup_row.index or pd.isna(
        sample_setup_row.get("long_market_confirmation")
    )
