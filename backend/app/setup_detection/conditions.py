"""
Individual LONG/SHORT condition checks. Each function is a small, pure,
independently-testable comparison - engine.py composes them into the full
component set per bar. None of these fabricate a signal from missing data:
where an input is NaN, the comparison naturally evaluates to False (pandas
NaN comparisons are always False), never True.
"""
from __future__ import annotations

import pandas as pd


def above_vwap(close: pd.Series, vwap: pd.Series) -> pd.Series:
    return close > vwap


def below_vwap(close: pd.Series, vwap: pd.Series) -> pd.Series:
    return close < vwap


def ema_bullish_alignment(ema_fast: pd.Series, ema_slow: pd.Series) -> pd.Series:
    return ema_fast > ema_slow


def ema_bearish_alignment(ema_fast: pd.Series, ema_slow: pd.Series) -> pd.Series:
    return ema_fast < ema_slow


def rsi_in_zone(rsi: pd.Series, low: float, high: float) -> pd.Series:
    if low >= high:
        raise ValueError("low threshold must be less than high threshold")
    return (rsi >= low) & (rsi <= high)


def adx_bullish(adx: pd.Series, plus_di: pd.Series, minus_di: pd.Series, adx_min: float) -> pd.Series:
    return (adx >= adx_min) & (plus_di > minus_di)


def adx_bearish(adx: pd.Series, plus_di: pd.Series, minus_di: pd.Series, adx_min: float) -> pd.Series:
    return (adx >= adx_min) & (minus_di > plus_di)


def volume_above_average(volume: pd.Series, average_volume: pd.Series) -> pd.Series:
    return volume > average_volume


def relative_volume_confirmed(relative_volume: pd.Series, minimum: float) -> pd.Series:
    return relative_volume >= minimum


def relative_strength_bullish(relative_strength: pd.Series, minimum: float) -> pd.Series:
    return relative_strength > minimum


def relative_strength_bearish(relative_strength: pd.Series, minimum: float) -> pd.Series:
    return relative_strength < -minimum


def market_direction_bullish(nifty_ema_fast: pd.Series, nifty_ema_slow: pd.Series) -> pd.Series:
    return nifty_ema_fast > nifty_ema_slow


def market_direction_bearish(nifty_ema_fast: pd.Series, nifty_ema_slow: pd.Series) -> pd.Series:
    return nifty_ema_fast < nifty_ema_slow
