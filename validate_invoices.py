import os, json
from datetime import datetime
import pandas as pd
import great_expectations as gx

df = pd.read_json("data/dummy_invoices.json")
context = gx.get_context()
validator = context.sources.pandas_default.read_dataframe(df)

for col in ["invoice_id", "patient_id", "date"]:
    validator.expect_column_to_exist(col)
    validator.expect_column_values_to_not_be_null(col)

for col in ["invoice_id", "patient_id", "date", "total"]:
    validator.expect_column_to_exist(col)
    validator.expect_column_values_to_not_be_null(col)

validator.expect_column_values_to_be_of_type("invoice_id", "str")
validator.expect_column_values_to_be_of_type("patient_id", "str")
validator.expect_column_values_to_match_regex("date", r"^\d{4}-\d{2}-\d{2}$")
validator.expect_column_values_to_be_of_type("total", "float")

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

os.makedirs("validation_logs", exist_ok=True)
ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
summary = {
    "success": results["success"] if isinstance(results, dict) and "success" in results else getattr(results, "success", None),
    "run_id": str(getattr(results, "run_id", "")),
}
with open(f"validation_logs/invoices_{ts}.json","w") as f:
    json.dump(summary, f, indent=2)
print("Validation complete:", summary)
