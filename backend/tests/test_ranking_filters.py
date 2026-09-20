import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ranking.filters import RankingFilters, apply_filters, top_n  # noqa: E402


def make_ranked_df():
    return pd.DataFrame(
        {
            "rank": [1, 2, 3, 4],
            "symbol": ["AAA", "BBB", "CCC", "DDD"],
            "direction": ["LONG", "SHORT", "LONG", "NONE"],
            "entry_status": ["READY", "WATCH", "NONE", "NONE"],
            "opportunity_score": [80.0, 60.0, 45.0, 20.0],
            "risk_reward": [2.5, 1.5, None, 1.0],
            "relative_volume": [2.0, 1.3, 0.9, 1.1],
        }
    )


def test_filter_by_direction():
    df = make_ranked_df()
    result = apply_filters(df, RankingFilters(direction="LONG"))
    assert list(result["symbol"]) == ["AAA", "CCC"]
    assert list(result["rank"]) == [1, 2]  # re-ranked after filtering


def test_filter_by_entry_status():
    df = make_ranked_df()
    result = apply_filters(df, RankingFilters(entry_status="READY"))
    assert list(result["symbol"]) == ["AAA"]


def test_filter_by_min_score():
    df = make_ranked_df()
    result = apply_filters(df, RankingFilters(min_score=50.0))
    assert list(result["symbol"]) == ["AAA", "BBB"]


def test_filter_by_min_risk_reward_excludes_missing():
    df = make_ranked_df()
    result = apply_filters(df, RankingFilters(min_risk_reward=1.4))
    # CCC has no risk_reward (None) -> excluded, not treated as passing
    assert list(result["symbol"]) == ["AAA", "BBB"]


def test_filter_by_min_relative_volume():
    df = make_ranked_df()
    result = apply_filters(df, RankingFilters(min_relative_volume=1.2))
    assert list(result["symbol"]) == ["AAA", "BBB"]


def test_combined_filters():
    df = make_ranked_df()
    result = apply_filters(df, RankingFilters(direction="LONG", min_score=50.0))
    assert list(result["symbol"]) == ["AAA"]


def test_no_filters_returns_everything_unchanged():
    df = make_ranked_df()
    result = apply_filters(df, RankingFilters())
    assert list(result["symbol"]) == list(df["symbol"])


def test_filters_on_empty_dataframe():
    empty = make_ranked_df().iloc[0:0]
    result = apply_filters(empty, RankingFilters(direction="LONG"))
    assert result.empty


def test_top_n_selection():
    df = make_ranked_df()
    assert list(top_n(df, 1)["symbol"]) == ["AAA"]
    assert list(top_n(df, 3)["symbol"]) == ["AAA", "BBB", "CCC"]
    assert list(top_n(df, None)["symbol"]) == ["AAA", "BBB", "CCC", "DDD"]  # full universe


def test_top_n_rejects_non_positive():
    df = make_ranked_df()
    with pytest.raises(ValueError):
        top_n(df, 0)
