from __future__ import annotations

from typing import Any


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    consumed_fraction = min(1.0, actual_bad_rate / allowed_bad_rate)
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - consumed_fraction),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *,
    short_window_burn: float,
    long_window_burn: float,
    policy: str = "standard",
) -> dict[str, Any]:
    # Google SRE multi-window burn-rate policy
    # Short window = fast burn (1h), Long window = slow burn (6h)
    # Page only when BOTH windows exceed thresholds (reduces false positives from transient spikes)
    if short_window_burn >= 14.4 and long_window_burn >= 14.4:
        return {
            "page": True,
            "severity": "critical",
            "reason": f"fast_burn_both_windows: short={short_window_burn:.2f}, long={long_window_burn:.2f} (>=14.4x)",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
        }
    if short_window_burn >= 6.0 and long_window_burn >= 6.0:
        return {
            "page": True,
            "severity": "high",
            "reason": f"sustained_fast_burn: short={short_window_burn:.2f}, long={long_window_burn:.2f} (>=6.0x)",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
        }
    if short_window_burn >= 3.0 and long_window_burn >= 3.0:
        return {
            "page": True,
            "severity": "medium",
            "reason": f"sustained_slow_burn: short={short_window_burn:.2f}, long={long_window_burn:.2f} (>=3.0x)",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
        }
    if short_window_burn >= 3.0 or long_window_burn >= 3.0:
        return {
            "page": False,
            "severity": "warning",
            "reason": f"transient_elevated_burn: short={short_window_burn:.2f}, long={long_window_burn:.2f}",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
        }
    return {
        "page": False,
        "severity": "info",
        "reason": f"within_budget: short={short_window_burn:.2f}, long={long_window_burn:.2f}",
        "short_window_burn": short_window_burn,
        "long_window_burn": long_window_burn,
    }
