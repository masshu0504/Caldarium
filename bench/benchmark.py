import os, time
from pathlib import Path
import pandas as pd
from tqdm import tqdm

from triage import triage_folder
from parsers import parse_with_pdfplumber, parse_with_pdfminer, extract_fields
from table_extract import camelot_extract, tabula_extract, pick_first_table, load_ground_truth_lineitems
from metrics import exact_match, numeric_delta_ok, cell_match_rate

PDF_DIR = Path(os.getenv("PDF_DIR", "bench/data/pdfs"))
GT_FIELDS_CSV = Path(os.getenv("GT_FIELDS_CSV", "bench/data/ground_truth/invoice_fields.csv"))
GT_LINEITEMS_DIR = Path(os.getenv("GT_LINEITEMS_DIR", "bench/data/ground_truth/line_items"))
OUT_DIR = Path(os.getenv("OUT_DIR", "bench/outputs"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

def run_text_benchmark():
    gt = pd.read_csv(GT_FIELDS_CSV)
    records = []
    for _, row in gt.iterrows():
        filename = row["filename"]
        truth_inv, truth_pat, truth_total = row["invoice_id"], row["patient_id"], row["total_amount"]
        pdf_path = PDF_DIR / filename
        if not pdf_path.exists():
            continue
        for engine, fn in [("pdfplumber", parse_with_pdfplumber), ("pdfminer", parse_with_pdfminer)]:
            t0 = time.time()
            text = fn(pdf_path)
            elapsed = round(time.time() - t0, 3)
            fields = extract_fields(text)
            records.append({
                "filename": filename, "engine": engine, "elapsed_s": elapsed,
                "pred_invoice_id": fields["invoice_id"], "pred_patient_id": fields["patient_id"],
                "pred_total_amount": fields["total_amount"],
                "em_invoice_id": exact_match(fields["invoice_id"], truth_inv),
                "em_patient_id": exact_match(fields["patient_id"], truth_pat),
                "num_total_ok": numeric_delta_ok(fields["total_amount"], truth_total, tol=0.01)
            })
    df = pd.DataFrame(records)
    df.to_csv(OUT_DIR / "text_parser_results.csv", index=False)
    agg = (df.groupby("engine").agg(
        exact_invoice_rate=("em_invoice_id", "mean"),
        exact_patient_rate=("em_patient_id", "mean"),
        total_within_tol_rate=("num_total_ok", "mean"),
        avg_latency_s=("elapsed_s", "mean"),
        n=("filename", "count"))
        .reset_index())
    agg.to_csv(OUT_DIR / "text_parser_summary.csv", index=False)
    return df, agg

def run_table_benchmark(use_camelot=True, use_tabula=True):
    rows = []
    for pdf in tqdm(sorted(PDF_DIR.glob("*.pdf"))):
        gt_df = load_ground_truth_lineitems(GT_LINEITEMS_DIR, pdf.name)
        if use_camelot:
            cams = camelot_extract(pdf)
            for variant, dfs in cams.items():
                pred = pick_first_table(dfs)
                rows.append({"filename": pdf.name, "extractor": variant, "cell_match_rate": cell_match_rate(pred, gt_df)})
        if use_tabula:
            tabs = tabula_extract(pdf)
            for variant, dfs in tabs.items():
                pred = pick_first_table(dfs)
                rows.append({"filename": pdf.name, "extractor": variant, "cell_match_rate": cell_match_rate(pred, gt_df)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "table_results.csv", index=False)
    agg = (df.dropna(subset=["cell_match_rate"])
             .groupby("extractor").agg(avg_cell_match_rate=("cell_match_rate","mean"), n=("filename","count"))
             .reset_index())
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
