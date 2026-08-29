#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import great_expectations as gx
except ImportError as exc:
    raise SystemExit("great_expectations is not installed. Run: pip install -r requirements.txt") from exc


def build_suite(context):
    suite_name = "orders_suite"
    try:
        context.suites.delete(suite_name)
    except Exception:
        pass
    suite = context.suites.add(
        gx.ExpectationSuite(
            name=suite_name,
            expectations=[
                gx.expectations.ExpectColumnValuesToNotBeNull(column="order_id", severity="critical"),
                gx.expectations.ExpectColumnValuesToBeUnique(column="order_id", severity="critical"),
                gx.expectations.ExpectColumnValuesToNotBeNull(column="customer_id", severity="critical"),
                gx.expectations.ExpectColumnValuesToNotBeNull(column="amount", severity="critical"),
                gx.expectations.ExpectColumnValuesToBeBetween(column="amount", min_value=0, severity="critical"),
                gx.expectations.ExpectColumnValuesToBeInSet(column="currency", value_set=["USD", "VND"], severity="critical"),
                gx.expectations.ExpectColumnValuesToBeInSet(
                    column="status",
                    value_set=["pending", "completed", "refunded", "cancelled"],
                    severity="warning",
                ),
                gx.expectations.ExpectColumnValuesToNotBeNull(column="created_at", severity="critical"),
                gx.expectations.ExpectColumnValuesToNotBeNull(column="updated_at", severity="critical"),
            ],
        )
    )
    return suite


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "incoming" / "orders.csv")
    context = gx.get_context()

    data_source = context.data_sources.add_pandas("orders_pandas")
    asset = data_source.add_dataframe_asset(name="orders_dataframe")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole_orders")

    suite = build_suite(context)

    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="orders_validation",
            data=batch_definition,
            suite=suite,
        )
    )

    checkpoint = context.checkpoints.add(
        gx.Checkpoint(
            name="orders_checkpoint",
            validation_definitions=[validation_definition],
            actions=[
                gx.checkpoint.UpdateDataDocsAction(name="update_docs"),
            ],
        )
    )

    result = checkpoint.run(batch_parameters={"dataframe": df})

    all_ok = bool(result.success)
    for _key, val_result in result.run_results.items():
        for evr in val_result.results:
            success = bool(evr.success)
            ename = evr.expectation_config.type if hasattr(evr, "expectation_config") else "unknown"
            print(f"{ename:<50} success={success}")

    print("\nGX Suite result:", "PASS" if all_ok else "FAIL")


if __name__ == "__main__":
    main()
