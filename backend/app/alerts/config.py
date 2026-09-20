"""
Alert configuration: which alert types are enabled, which delivery
channel(s) each type uses, and the score thresholds for the two
score-crossing alert types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Set


class AlertType(str, Enum):
    SCORE_CROSSES_80 = "SCORE_CROSSES_80"
    SCORE_CROSSES_90 = "SCORE_CROSSES_90"
    LONG_SETUP = "LONG_SETUP"
    SHORT_SETUP = "SHORT_SETUP"
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"
    VWAP_RECLAIM = "VWAP_RECLAIM"
    VWAP_REJECTION = "VWAP_REJECTION"
    ENTRY_TRIGGER = "ENTRY_TRIGGER"
    STOP_LOSS = "STOP_LOSS"
    TARGET = "TARGET"


class AlertChannel(str, Enum):
    DASHBOARD = "DASHBOARD"
    BROWSER_NOTIFICATION = "BROWSER_NOTIFICATION"
    SOUND = "SOUND"


@dataclass
class AlertConfig:
    enabled_types: Set[AlertType] = field(default_factory=lambda: set(AlertType))
    # Per-type channel overrides; any type not listed here falls back to
    # default_channels. Every channel is "start with" scope (Phase 11
    # spec) - dashboard is always safe/available, browser notification
    # and sound require the frontend to have permission/be unmuted.
    channels: Dict[AlertType, Set[AlertChannel]] = field(default_factory=dict)
    default_channels: Set[AlertChannel] = field(
        default_factory=lambda: {AlertChannel.DASHBOARD, AlertChannel.BROWSER_NOTIFICATION, AlertChannel.SOUND}
    )
    score_threshold_80: float = 80.0
    score_threshold_90: float = 90.0

    def channels_for(self, alert_type: AlertType) -> Set[AlertChannel]:
        return self.channels.get(alert_type, self.default_channels)
