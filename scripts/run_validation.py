import argparse, json, csv
from pathlib import Path
from jsonschema import Draft7Validator
from typing import List, Dict, Any

# --- Configuration adapted to finalized schema ---
# Field names reflect the finalized invoice schema (invoice_v1_reset.json).
REQUIRED_FIELDS = [
    "invoice_number", "invoice_date", "due_date",
    "patient_name", "subtotal_amount", "total_amount", "line_items"
]

# Optional fields we want presence stats for (purely informational)
OPTIONAL_FIELDS = [
    "patient_id", "patient_age", "patient_address", "patient_phone", "patient_email",
    "admission_date", "discharge_date", "provider_name", "bed_id", "discount_amount"
]


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def as_float(x):
    try:
        return float(x)
    except Exception:
        return None


def as_str(x):
    return "" if x is None else str(x)


def check_doc_rules(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Custom (non-schema) checks aligned to the finalized schema.

    - Required fields exist and are non-empty
    - Optional presence flags
    - Cross-field logic:
        * due_date >= invoice_date (lexicographic compare is fine for YYYY-MM-DD)
        * discharge_date >= admission_date (if both present)
        * total_amount >= subtotal_amount - 1e-9 (never less than subtotal)
        * If discount_amount is present: total_amount == subtotal_amount - discount_amount (±0.01)
        * Sum of line_items.amount equals subtotal_amount (±0.01)
    - Line item checks:
        * Each item needs description, code, amount
    """
    results = {
        "doc_id": doc.get("invoice_number") or doc.get("patient_id") or "",
        "required_pass": True,
        "missing_required": [],
        "optional_present_flags": {k: False for k in OPTIONAL_FIELDS},
        "crossfield_failures": [],
        "lineitem_failures": [],
    }

    # Required fields present?
    for k in REQUIRED_FIELDS:
        if doc.get(k) in (None, "", []):
            results["required_pass"] = False
            results["missing_required"].append(k)

    # Optional flags
    for k in OPTIONAL_FIELDS:
        v = doc.get(k)
        results["optional_present_flags"][k] = not (v in (None, "", []))

    # Cross-field logic
    inv_date = doc.get("invoice_date")
    due_date = doc.get("due_date")
    if inv_date and due_date:
        if as_str(due_date) < as_str(inv_date):
            results["crossfield_failures"].append("due_date < invoice_date")

    # Admission / discharge (if provided)
    admit = doc.get("admission_date")
    discharge = doc.get("discharge_date")
    if admit and discharge:
        if as_str(discharge) < as_str(admit):
            results["crossfield_failures"].append("discharge_date < admission_date")

    subtotal = as_float(doc.get("subtotal_amount"))
    total = as_float(doc.get("total_amount"))
    discount = as_float(doc.get("discount_amount")) if doc.get("discount_amount") not in (None, "") else None

    if subtotal is not None and total is not None:
       # Total should not be less than subtotal (schema description implies discounts reduce from subtotal)
       if total + 1e-9 < subtotal:
           results["crossfield_failures"].append("total_amount < subtotal_amount")
       # If discount is provided, enforce total ≈ subtotal - discount
       if discount is not None:
           if abs((subtotal - discount) - total) > 0.01:
               results["crossfield_failures"].append(
                   "total_amount != subtotal_amount - discount_amount (±0.01)"
               )


    # Line items checks
    line_items = doc.get("line_items")
    if isinstance(line_items, list):
        if len(line_items) == 0:
            results["lineitem_failures"].append("line_items empty")
        else:
            for idx, item in enumerate(line_items):
                if not item.get("description"):
                    results["lineitem_failures"].append(f"line_items[{idx}].description missing")
                if not item.get("code"):
                    results["lineitem_failures"].append(f"line_items[{idx}].code missing")
                amt = as_float(item.get("amount"))
                if amt is None:
                    results["lineitem_failures"].append(f"line_items[{idx}].amount missing")
            if subtotal is not None:
                s = sum(as_float(item.get("amount")) or 0 for item in line_items)
                if abs(s - subtotal) > 0.01:
                    results["crossfield_failures"].append(
                        "sum(line_items.amount) != subtotal_amount (±0.01)"
                    )
    else:
        results["lineitem_failures"].append("line_items not a list")

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="Folder with *.json invoices")
    ap.add_argument("--out", required=True, help="Output folder")
    ap.add_argument("--schema", required=False, help="Path to JSON Schema file (e.g., invoice_v1_reset.json)")
    args = ap.parse_args()

    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load schema (optional)
    schema = None
    validator = None
    if args.schema:
        schema = read_json(Path(args.schema))
        validator = Draft7Validator(schema)

    rows: List[Dict[str, Any]] = []
    for p in sorted(data_dir.rglob("*.json")):
        try:
            doc = read_json(p)

            # Schema errors (if schema provided)
            schema_errors = []
            if validator is not None:
                errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
                for e in errs:
                    loc = ".".join([str(x) for x in e.path]) or "<root>"
                    schema_errors.append(f"{loc}: {e.message}")

            # Custom checks
            r = check_doc_rules(doc)
            r["path"] = str(p)
            r["schema_errors"] = schema_errors
            rows.append(r)

        except Exception as e:
            rows.append({
                "doc_id": "",
                "required_pass": False,
                "missing_required": ["_read_error_"],
                "optional_present_flags": {k: False for k in OPTIONAL_FIELDS},
                "crossfield_failures": [f"read_error: {e}"],
                "lineitem_failures": [],
                "schema_errors": [f"read_error: {e}"],
                "path": str(p)
            })

    # Aggregates
    total = len(rows) or 1
    req_pass = sum(1 for d in rows if d["required_pass"]) / total
    optional_presence = {
        k: (sum(1 for d in rows if d["optional_present_flags"][k]) / total)
        for k in OPTIONAL_FIELDS
    }
    crossfield_fail_count = sum(len(d["crossfield_failures"]) for d in rows)
    schema_fail_count = sum(1 for d in rows if d.get("schema_errors"))

    # CSV (keep the same filename/format for downstream compatibility)
    csv_path = out_dir / "validation_results_v1.1.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "path","doc_id","required_pass","missing_required",
            "optional_present_billing_address","optional_present_notes","optional_present_tax_id",
            "crossfield_failures","lineitem_failures","schema_errors"
        ])
        for d in rows:
            # Maintain legacy optional columns (billing_address/notes/tax_id) as False for back-compat.
            # Presence for new optional fields is kept in the markdown summary.
            w.writerow([
                d.get("path",""),
                d.get("doc_id",""),
                d.get("required_pass",False),
                ";".join(d.get("missing_required",[])),
                False,  # optional_present_billing_address (legacy)
                False,  # optional_present_notes (legacy)
                False,  # optional_present_tax_id (legacy)
                ";".join(d.get("crossfield_failures",[])),
                ";".join(d.get("lineitem_failures",[])),
                "; ".join(d.get("schema_errors",[])),
            ])

    # Markdown summary (adds visibility for the new optional fields)
    md = out_dir / "validation_report.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Validation Report (v1.1)\n\n")
        f.write("## Summary\n")
        f.write(f"- Required-field pass %: {req_pass*100:.1f}%\n")
        f.write(f"- Optional-field presence rates (new fields): {json.dumps(optional_presence)}\n")
        f.write(f"- Cross-field failure count: {crossfield_fail_count}\n")
        if validator is not None:
            f.write(f"- Files with schema errors: {schema_fail_count} of {total}\n")
        f.write("\nSee `validation_results_v1.1.csv` for full details.\n")

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {md}")


if __name__ == "__main__":
    main()