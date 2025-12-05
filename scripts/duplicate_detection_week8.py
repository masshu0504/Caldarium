#!/usr/bin/env python

import json
from pathlib import Path

import pandas as pd

# -------------------------------------------------------------------
# CONFIG — UPDATE THESE PATHS TO MATCH YOUR PROJECT
# -------------------------------------------------------------------

INVOICE_DIR = Path("parser_json_output")
CONSENT_DIR = Path("json_consents")
INTAKE_DIR  = Path("json_intakes")

OUTPUT_PATH = Path("output") / "duplicate_detection_summary_week8.csv"

# Use at least three fields for comparison; present in invoices + consents
DUP_KEYS = ["patient_name", "patient_id", "provider_name"]


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def load_records_from_file(path: Path):
    """
    Load one JSON file and yield record dicts.
    Handles:
      - A single JSON object
      - A list of JSON objects
    """
    with path.open() as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"[WARN] Skipping invalid JSON: {path}")
            return

    if isinstance(data, dict):
        yield data
    elif isinstance(data, list):
        for rec in data:
            if isinstance(rec, dict):
                yield rec
    # ignore other types


def load_records_from_dir(doc_type: str, directory: Path):
    """
    Load all records from a given directory and tag them with doc_type.
    """
    rows = []

    if not directory.exists():
        print(f"[INFO] Directory does not exist, skipping: {directory}")
        return rows

    for path in sorted(directory.glob("*.json")):
        for rec in load_records_from_file(path):
            row = {
                "doc_type": doc_type,
                "source_file": str(path),
            }
            # Copy over duplicate key fields (may be missing / None)
            for key in DUP_KEYS:
                row[key] = rec.get(key)
            rows.append(row)

    return rows


def detect_duplicates():
    all_rows = []

    # Load from each doc-type directory
    all_rows += load_records_from_dir("invoice", INVOICE_DIR)
    all_rows += load_records_from_dir("consent", CONSENT_DIR)
    all_rows += load_records_from_dir("intake",  INTAKE_DIR)

    if not all_rows:
        print("[INFO] No records found in any directory; nothing to do.")
        return None, None, None

    df = pd.DataFrame(all_rows)

    # We NO LONGER drop rows with missing keys — we group including NaNs.
    total_records = len(df)

    # Group by duplicate keys (NaNs included using dropna=False)
    grouped = (
        df
        .groupby(DUP_KEYS, dropna=False)
        .size()
        .reset_index(name="record_count")
    )

    # Groups with more than one record are duplicates
    dup_groups = grouped[grouped["record_count"] > 1]

    if dup_groups.empty:
        print("[INFO] No duplicate groups found based on keys:", DUP_KEYS)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        dup_groups.to_csv(OUTPUT_PATH, index=False)
        # Duplicate reduction is 0.0 (no duplicates)
        return df, grouped, 0.0

    # Merge back to get full rows (with doc_type + source_file)
    duplicates_full = dup_groups.merge(df, on=DUP_KEYS, how="left")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    duplicates_full.to_csv(OUTPUT_PATH, index=False)

    # Duplicate Reduction (%) = (1 - unique_records / total_records) * 100
    unique_records = grouped.shape[0]
    duplicate_reduction_pct = (1 - unique_records / total_records) * 100

    return df, grouped, duplicate_reduction_pct


def main():
    df_all, grouped, duplicate_reduction_pct = detect_duplicates()

    if df_all is None:
        # No data at all
        return

    if duplicate_reduction_pct is None:
        print("Duplicate Reduction (%): N/A")
    else:
        print(f"Duplicate Reduction (%): {duplicate_reduction_pct:.2f}")

    print(f"Duplicate detection summary written to: {OUTPUT_PATH}")

    # When you're ready later, here's where you'll call:
    #   save_duplicate_reduction_metric(duplicate_reduction_pct)
    # using the helper you pasted earlier.


if __name__ == "__main__":
    main()
