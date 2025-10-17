import os, time
from pathlib import Path
import pandas as pd
from tqdm import tqdm

from triage import triage_folder
from parsers import extract_line_items, parse_with_pdfplumber, parse_with_pdfminer, extract_fields
from table_extract import camelot_extract, tabula_extract, pick_first_table, load_ground_truth_lineitems
from metrics import exact_match, numeric_delta_ok, cell_match_rate
from audit_logger import audit_logger, log_parsing_success, log_parsing_error

PDF_DIR = Path(os.getenv("PDF_DIR", "minio_buckets/invoices"))
GT_FIELDS_CSV = Path(os.getenv("GT_FIELDS_CSV", "bench/data/ground_truth/invoice_fields.csv"))
GT_LINEITEMS_DIR = Path(os.getenv("GT_LINEITEMS_DIR", "bench/data/ground_truth/line_items"))
OUT_DIR = Path(os.getenv("OUT_DIR", "bench/outputs"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

def run_text_benchmark():
    gt = pd.read_csv(GT_FIELDS_CSV)
    records = []
    for _, row in gt.iterrows():
        filename = row["filename"]
        truth_inv = row["invoice_number"]
        truth_pat = row["patient_id"]
        truth_date = row["invoice_date"]
        truth_subtotal = row["subtotal_amount"]
        truth_total = row["total_amount"]
        truth_line_items = row["line_items"]
        pdf_path = PDF_DIR / filename
        if not pdf_path.exists():
            continue
        for engine, fn in [("pdfplumber", parse_with_pdfplumber), ("pdfminer", parse_with_pdfminer)]:
            t0 = time.time()
            text = fn(pdf_path)
            elapsed = round(time.time() - t0, 3)
            fields = extract_fields(text)
            line_items = extract_line_items(pdf_path)
            fields["line_items"] = line_items
            
            # Audit logging
            details = {
                "extracted_fields": fields,
                "processing_time_ms": elapsed * 1000,
                "engine_used": engine,
                "text_length": len(text) if text else 0
            }
            
            # Determine error type based on extraction results
            missing_fields = [k for k, v in fields.items() if v is None or v == ""]
            if missing_fields:
                error_type = "MISSING_FIELD"
                details["missing_fields"] = missing_fields
                log_parsing_error(filename, "parse", error_type, details)
            else:
                log_parsing_success(filename, "parse", details)

            records.append({
                "filename": filename,
                "engine": engine,
                "elapsed_s": elapsed,
                "pred_invoice_number": fields.get("invoice_number"),
                "pred_patient_id": fields.get("patient_id"),
                "pred_invoice_date": fields.get("invoice_date"),
                "pred_subtotal_amount": fields.get("subtotal_amount"),
                "pred_total_amount": fields.get("total_amount"),
                "pred_line_items": str(fields.get("line_items")),
                "em_invoice_number": exact_match(fields.get("invoice_number"), truth_inv),
                "em_patient_id": exact_match(fields.get("patient_id"), truth_pat),
                "em_invoice_date": exact_match(fields.get("invoice_date"), truth_date),
                "num_subtotal_ok": numeric_delta_ok(fields.get("subtotal_amount"), truth_subtotal, tol=0.01),
                "num_total_ok": numeric_delta_ok(fields.get("total_amount"), truth_total, tol=0.01),
                "em_line_items": exact_match(str(fields.get("line_items")), str(truth_line_items))
            })
    df = pd.DataFrame(records)
    df.to_csv(OUT_DIR / "text_parser_results.csv", index=False)
    agg = (df.groupby("engine").agg(
        exact_invoice_rate=("em_invoice_number", "mean"),
        exact_patient_rate=("em_patient_id", "mean"),
        exact_date_rate=("em_invoice_date", "mean"),
        subtotal_within_tol_rate=("num_subtotal_ok", "mean"),
        total_within_tol_rate=("num_total_ok", "mean"),
        line_items_exact_rate=("em_line_items", "mean"),
        avg_latency_s=("elapsed_s", "mean"),
        n=("filename", "count"))
        .reset_index())
    agg.to_csv(OUT_DIR / "text_parser_summary.csv", index=False)
    return df, agg

def run_table_benchmark(use_camelot=True, use_tabula=True):
    rows = []
    for pdf in tqdm(sorted(PDF_DIR.glob("*.pdf"))):
        gt_df = load_ground_truth_lineitems(GT_LINEITEMS_DIR, pdf.name)

        def add_result(variant, dfs):
            pred = pick_first_table(dfs)
            rate = None
            if pred is not None and not gt_df.empty:
                rate = cell_match_rate(pred, gt_df)
            rows.append({
                "filename": pdf.name,
                "extractor": variant,
                "cell_match_rate": rate
            })

        if use_camelot:
            cams = camelot_extract(pdf)
            for variant, dfs in cams.items():
                add_result(variant, dfs)

        if use_tabula:
            tabs = tabula_extract(pdf)
            for variant, dfs in tabs.items():
                add_result(variant, dfs)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "table_results.csv", index=False)

    # Only aggregate rows with a numeric score
    agg = (df.dropna(subset=["cell_match_rate"])
             .groupby("extractor", as_index=False)
             .agg(avg_cell_match_rate=("cell_match_rate", "mean"),
                  n=("filename", "count")))
    agg.to_csv(OUT_DIR / "table_summary.csv", index=False)
    return df, agg

if __name__ == "__main__":
    print("Step 1: Triage…")
    triage_folder(PDF_DIR, OUT_DIR / "triage_log.csv")
    print("Step 2: Text parsers…")
    run_text_benchmark()
    print("Step 3: Tables…")
    run_table_benchmark(use_camelot=True, use_tabula=True)
    print("Done. See bench/outputs/")
