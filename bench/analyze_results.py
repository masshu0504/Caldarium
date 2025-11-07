import pandas as pd

# Path to your generated CSV file
df = pd.read_csv("bench/outputs/metrics_by_document.csv")

# Only rows where both sides had values
both = df[(df["gt_present"] == 1) & (df["parser_present"] == 1)].copy()

# 1) Error rate by field
err_by_field = (1 - both.groupby("field")["match"].mean()).sort_values(ascending=False)
print("Error rate by field (%):\n", (err_by_field * 100).round(1))

# 2) Most common failure types by field
fails = both[~both["match"]]
print("\nTop failure types by field:\n",
      fails.groupby(["field", "match_type"]).size().sort_values(ascending=False).head(20))

# 3) Documents with most mismatches
print("\nDocs with most both-present mismatches:\n",
      fails.groupby("document").size().sort_values(ascending=False).head(15))

# 4) Show details for worst-performing field
if not err_by_field.empty:
    worst_field = err_by_field.index[0]
    print(f"\nSample failures for field={worst_field}:\n",
          fails[fails["field"] == worst_field][["document", "match_type", "gt_value", "parser_value"]]
          .head(10)
          .to_string(index=False))
