from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    ratio_threshold: float = 3.0,
) -> dict[str, Any]:
    cur = np.asarray(list(current_values), dtype=float)
    base = np.asarray(list(baseline_values), dtype=float)
    if cur.size == 0 or base.size == 0:
        return {"is_anomaly": False, "score": 0.0, "method": "ks_test", "reason": "empty_input"}

    cur_mean = float(np.mean(cur))
    base_mean = float(np.mean(base))

    try:
        from scipy.stats import ks_2samp
        stat, pvalue = ks_2samp(base, cur)
        # ponytail: small samples reduce KS power; combine with mean-ratio guard
        mean_ratio = max(abs(cur_mean / base_mean), abs(base_mean / cur_mean)) if base_mean != 0 and cur_mean != 0 else float("inf")
        is_anomaly = bool(pvalue < 0.05) or bool(mean_ratio >= ratio_threshold)
        return {
            "is_anomaly": is_anomaly,
            "score": float(stat),
            "p_value": float(pvalue),
            "mean_ratio": float(mean_ratio) if mean_ratio != float("inf") else None,
            "method": "ks_test+mean_ratio",
            "reason": f"ks_stat={stat:.4f}, p_value={pvalue:.6f}, mean_ratio={mean_ratio:.3f}",
        }
    except ImportError:
        pass

    cur_std = float(np.std(cur))
    base_std = float(np.std(base))
    pooled_std = max(np.sqrt((cur_std ** 2 + base_std ** 2) / 2), 1e-9)
    score = abs(cur_mean - base_mean) / pooled_std
    return {
        "is_anomaly": bool(score >= ratio_threshold),
        "score": float(score),
        "method": "cohens_d",
        "reason": f"baseline_mean={base_mean:.3f}, current_mean={cur_mean:.3f}, cohens_d={score:.3f}",
    }
