import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.risk_management.config import RiskConfig  # noqa: E402


def test_effective_max_risk_amount_uses_percentage_when_smaller():
    config = RiskConfig(account_capital=100000.0, risk_per_trade_pct=0.01, max_loss_per_trade=5000.0)
    # 1% of 100000 = 1000, well below the 5000 hard cap
    assert config.effective_max_risk_amount() == pytest.approx(1000.0)


def test_effective_max_risk_amount_uses_hard_cap_when_smaller():
    config = RiskConfig(account_capital=1000000.0, risk_per_trade_pct=0.05, max_loss_per_trade=2000.0)
    # 5% of 1,000,000 = 50,000, way above the 2000 hard cap - cap wins
    assert config.effective_max_risk_amount() == pytest.approx(2000.0)


def test_validate_accepts_sensible_defaults():
    RiskConfig(account_capital=100000.0).validate()  # must not raise


def test_validate_rejects_invalid_values():
    bad_cases = [
        {"account_capital": 0.0},
        {"account_capital": -100.0},
        {"account_capital": 100000.0, "risk_per_trade_pct": 0.0},
        {"account_capital": 100000.0, "risk_per_trade_pct": 1.5},
        {"account_capital": 100000.0, "max_daily_loss": 0.0},
        {"account_capital": 100000.0, "max_open_positions": 0},
        {"account_capital": 100000.0, "max_trades_per_day": 0},
        {"account_capital": 100000.0, "max_position_value": 0.0},
        {"account_capital": 100000.0, "max_loss_per_trade": 0.0},
        {"account_capital": 100000.0, "min_risk_reward": 0.0},
        {"account_capital": 100000.0, "max_data_age_seconds": 0.0},
    ]
    for kwargs in bad_cases:
        with pytest.raises(ValueError):
            RiskConfig(**kwargs).validate()
