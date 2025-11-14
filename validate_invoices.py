import os, json
from datetime import datetime, date
import pandas as pd
import great_expectations as gx


def validate(invoice):
    # --- Load data & get a validator ---
    #df = pd.read_json("data/dummy_invoices.json")
    df = pd.read_json(invoice)
    context = gx.get_context()
    validator = context.sources.pandas_default.read_dataframe(df)

    # ===== STRICTER EXPECTATIONS (add here) =====
    today = date.today().strftime("%Y-%m-%d")

    # Required columns (fail clearly if missing)
    validator.expect_table_columns_to_contain_set(
        column_set=["invoice_id", "patient_id", "date", "total"]
    )

    # Presence
    for col in ["invoice_id", "patient_id", "date", "total"]:
        validator.expect_column_values_to_not_be_null(col)

    # Types / formats
    validator.expect_column_values_to_be_of_type("invoice_id", "str")
    validator.expect_column_values_to_be_of_type("patient_id", "str")
    validator.expect_column_values_to_be_of_type("total", "float")
    validator.expect_column_values_to_match_regex("date", r"^\d{4}-\d{2}-\d{2}$")
    validator.expect_column_values_to_match_strftime_format("date", "%Y-%m-%d")

    # Totals numeric and non-negative
    validator.expect_column_values_to_be_between(
        "total", min_value=0, allow_cross_type_comparisons=True
    )

    # Optional consent_type allowed set (only if column exists)
    if "consent_type" in df.columns:
        validator.expect_column_values_to_be_in_set(
            "consent_type", ["written", "verbal", "implied"]
        )

    # Optional DOB not in future (only if column exists)
    if "dob" in df.columns:
        validator.expect_column_values_to_match_regex("dob", r"^\d{4}-\d{2}-\d{2}$")
        validator.expect_column_values_to_match_strftime_format("dob", "%Y-%m-%d")
        validator.expect_column_values_to_be_between("dob", max_value=today)
    # ===== END STRICTER BLOCK =====

    # --- Build suite & checkpoint ---
    suite = validator.get_expectation_suite(discard_failed_expectations=False)
    suite.expectation_suite_name = "invoices_suite"
    context.add_or_update_expectation_suite(expectation_suite=suite)

    context.add_or_update_checkpoint(
        name="invoices_checkpoint",
        validations=[{
            "batch_request": validator.active_batch.batch_request,
            "expectation_suite_name": suite.expectation_suite_name
        }]
    )

    results = context.run_checkpoint("invoices_checkpoint")

    # --- Persist a tiny run summary ---
    os.makedirs("validation_logs", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "success": results["success"] if isinstance(results, dict) and "success" in results else getattr(results, "success", None),
        "run_id": str(getattr(results, "run_id", "")),
    }
    with open(f"validation_logs/invoices_{ts}.json","w") as f:
        json.dump(summary, f, indent=2)
    print("Validation complete:", summary)
    if isinstance(results, dict) and "success" in results:
        return True
    else:
        return False