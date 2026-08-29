from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def zscore_detector(current: float, history: Iterable[float], threshold: float = 3.0) -> dict[str, Any]:
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "zscore", "reason": "insufficient_history"}
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(current: float, history: Iterable[float], threshold: float = 3.5) -> dict[str, Any]:
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "mad", "reason": "insufficient_history"}
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0:
        # ponytail: fallback to MAD+epsilon when all values identical; upgrade to EWMA if needed
        eps = max(abs(median) * 1e-9, 1e-9)
        modified_z = 0.6745 * abs(float(current) - median) / eps
        return {
            "is_anomaly": bool(modified_z > threshold),
            "score": float(modified_z),
            "method": "mad",
            "reason": f"median={median:.3f}, mad=0 (eps={eps:.2e}), threshold={threshold}",
        }
    modified_z = 0.6745 * abs(float(current) - median) / mad
    return {
        "is_anomaly": bool(modified_z > threshold),
        "score": float(modified_z),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, threshold={threshold}",
    }


def _ewma_baseline(history: Iterable[float], span: int = 7) -> tuple[float, float]:
    values = np.asarray(list(history), dtype=float)
    alpha = 2.0 / (span + 1)
    ewma = values[0]
    for v in values[1:]:
        ewma = alpha * v + (1 - alpha) * ewma
    residuals = values - np.array([alpha * values[i] + (1 - alpha) * (values[i - 1] if i > 0 else values[0]) for i in range(len(values))])
    std = float(np.std(residuals)) if len(residuals) > 1 else float(np.std(values))
    return float(ewma), max(std, 1e-9)


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if method == "mad":
        return mad_detector(current, history)
    if method == "zscore":
        return zscore_detector(current, history, threshold=threshold)
    if method == "auto":
        hist_list = list(history)
        ctx = context or {}

        same_seg = ctx.get("same_segment_history")
        if same_seg and len(same_seg) >= 3:
            result = mad_detector(current, same_seg, threshold=threshold)
            result["method"] = "auto:same_segment_mad"
            return result

        if len(hist_list) >= 14:
            ewma_val, ewma_std = _ewma_baseline(hist_list)
            score = abs(float(current) - ewma_val) / ewma_std
            result = {
                "is_anomaly": bool(score > threshold),
                "score": float(score),
                "method": "auto:ewma",
                "reason": f"ewma={ewma_val:.3f}, ewma_std={ewma_std:.3f}, threshold={threshold}",
            }
            mad_result = mad_detector(current, hist_list, threshold=threshold)
            if mad_result["is_anomaly"] and not result["is_anomaly"]:
                return mad_result
            mad_result["method"] = "auto:mad"
            if not result["is_anomaly"] and mad_result["is_anomaly"]:
                return mad_result
            return result

        if len(hist_list) >= 5:
            result = mad_detector(current, hist_list, threshold=threshold)
            result["method"] = "auto:mad"
            return result

        result = zscore_detector(current, hist_list, threshold=threshold)
        result["method"] = "auto:zscore"
        return result
    raise ValueError(f"Unsupported method: {method}")
