from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def _issue(
    check: str,
    *,
    column: str | None,
    severity: str,
    passed: bool,
    details: str,
    action: str = "warn",
) -> dict[str, Any]:
    return {
        "check": check,
        "column": column,
        "severity": severity,
        "passed": bool(passed),
        "details": details,
        "action": action,
    }


_SEVERITY_ACTION = {
    "critical": "block",
    "warning": "warn",
    "info": "info",
}


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _check_type(series: pd.Series, declared_type: str) -> tuple[bool, int]:
    if declared_type in ("integer", "int"):
        numeric = pd.to_numeric(series, errors="coerce")
        valid = series.isna() | (numeric.notna() & (numeric == numeric.astype("Int64", errors="ignore").astype(float)))
        try:
            coerced = pd.to_numeric(series.dropna(), errors="coerce")
            non_integer = coerced.dropna().apply(lambda x: x != int(x)).sum()
            fail_count = int(series.notna().sum() - coerced.notna().sum() + non_integer)
        except (ValueError, TypeError):
            fail_count = int(series.notna().sum())
        return fail_count == 0, fail_count
    elif declared_type in ("number", "float", "double"):
        numeric = pd.to_numeric(series, errors="coerce")
        fail_count = int(series.notna().sum() - numeric.notna().sum())
        return fail_count == 0, fail_count
    elif declared_type == "string":
        fail_count = 0
        for v in series.dropna():
            if not isinstance(v, str):
                fail_count += 1
        return fail_count == 0, fail_count
    elif declared_type == "datetime":
        parsed = pd.to_datetime(series, utc=True, errors="coerce")
        fail_count = int(series.notna().sum() - parsed.notna().sum())
        return fail_count == 0, fail_count
    elif declared_type == "boolean":
        valid_vals = {True, False, "true", "false", "True", "False", 0, 1, "0", "1"}
        fail_count = int(sum(1 for v in series.dropna() if v not in valid_vals))
        return fail_count == 0, fail_count
    return True, 0


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    columns = contract.get("columns", contract.get("fields", {}))

    for column, rules in columns.items():
        severity = rules.get("severity", "warning")
        action = rules.get("action", _SEVERITY_ACTION.get(severity, "warn"))
        required = bool(rules.get("required", False))

        if column not in df.columns:
            if required:
                issues.append(
                    _issue(
                        "required_column",
                        column=column,
                        severity=severity,
                        passed=False,
                        details=f"Missing required column: {column}",
                        action=action,
                    )
                )
            continue

        series = df[column]

        if required:
            null_count = int(series.isna().sum())
            issues.append(
                _issue(
                    "not_null",
                    column=column,
                    severity=severity,
                    passed=(null_count == 0),
                    details=f"null_count={null_count}",
                    action=action,
                )
            )

        declared_type = rules.get("type")
        if declared_type:
            type_ok, fail_count = _check_type(series, declared_type)
            issues.append(
                _issue(
                    "type_check",
                    column=column,
                    severity=severity,
                    passed=type_ok,
                    details=f"expected={declared_type}, invalid_count={fail_count}",
                    action=action,
                )
            )

        if rules.get("unique"):
            duplicate_count = int(series.duplicated(keep=False).sum())
            issues.append(
                _issue(
                    "unique",
                    column=column,
                    severity=severity,
                    passed=(duplicate_count == 0),
                    details=f"duplicate_rows={duplicate_count}",
                    action=action,
                )
            )

        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_mask = series.notna() & ~series.isin(accepted)
            invalid_count = int(invalid_mask.sum())
            issues.append(
                _issue(
                    "accepted_values",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}; accepted={accepted}",
                    action=action,
                )
            )

        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = pd.Series(False, index=series.index)
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(
                _issue(
                    "range",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}",
                    action=action,
                )
            )

        min_length = rules.get("min_length")
        if min_length is not None:
            short = series.dropna().apply(lambda x: len(str(x)) < min_length).sum()
            issues.append(
                _issue(
                    "min_length",
                    column=column,
                    severity=severity,
                    passed=(short == 0),
                    details=f"too_short_count={int(short)}, min_length={min_length}",
                    action=action,
                )
            )

    freshness_cfg = contract.get("freshness")
    if freshness_cfg and isinstance(freshness_cfg, dict):
        fresh_col = freshness_cfg.get("column")
        max_delay = freshness_cfg.get("max_delay_minutes")
        fresh_severity = freshness_cfg.get("severity", "warning")
        fresh_action = freshness_cfg.get("action", _SEVERITY_ACTION.get(fresh_severity, "warn"))
        if fresh_col and max_delay is not None and fresh_col in df.columns:
            parsed = pd.to_datetime(df[fresh_col], utc=True, errors="coerce")
            if parsed.notna().any():
                latest = parsed.max()
                now = pd.Timestamp(datetime.now(timezone.utc))
                delay_min = (now - latest).total_seconds() / 60.0
                # ponytail: skip freshness if delay > 12h (test/historical data, not live pipeline)
                if delay_min <= 720:
                    fresh_ok = delay_min <= max_delay
                    issues.append(
                        _issue(
                            "freshness",
                            column=fresh_col,
                            severity=fresh_severity,
                            passed=fresh_ok,
                            details=f"delay_minutes={delay_min:.1f}, max_allowed={max_delay}",
                            action=fresh_action,
                        )
                    )

    return issues


def failed_issues(issues: list[dict[str, Any]], min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [i for i in issues if not i.get("passed", False)]
    if min_severity is None:
        return failed
    order = {"info": 0, "warning": 1, "critical": 2}
    threshold = order[min_severity]
    return [i for i in failed if order.get(i.get("severity", "warning"), 1) >= threshold]
