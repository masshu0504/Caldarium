# Benchmark Report — v0.1
**Date:** October 24, 2025  
**Author:** Isabella Siu  
**Module:** `benchmarker_v0.1.py`

---

## 1. Overview
This benchmark evaluates the **Minna parser JSON outputs** against the **Ground Truth (GT)** invoices across 3 shared documents:
- `invoice_T1_gen1`
- `invoice_T1_gen2`
- `invoice_T1_gen3`

Each field was aligned by schema name and document ID.  
The script computed per-field **Precision**, **Recall**, and **F1-score**, and exported results to:
- `benchmark_v0.1.json`
- `benchmark_v0.1.csv`
- `metrics_by_field.csv`
- `metrics_by_document.csv`

---

## 2. Environment
| Component | Version / Detail |
|------------|------------------|
| Python | 3.x (WSL) |
| pandas | 2.2.2 |
| numpy | 1.26.4 |
| Platform | Ubuntu (WSL2) |
| Benchmark Version | v0.1 |
| Random Seed | 42 |

---

## 3. Results Summary

| Field | Precision | Recall | F1 |
|-------|------------|--------|----|
| invoice_number | 1.00 | 1.00 | 1.00 |
| due_date | 0.00 | 0.00 | 0.00 |
| patient_name | 1.00 | 1.00 | 1.00 |
| subtotal_amount | 1.00 | 1.00 | 1.00 |
| invoice_date | 1.00 | 1.00 | 1.00 |
| total_amount | 1.00 | 1.00 | 1.00 |
| line_items | 0.33 | 0.33 | 0.33 |

**Overall Accuracy:** `0.81`

---

## 4. Parser Misses & Observations
- **`due_date`**: consistently missing in parser output → likely due to regex omission.
- **`line_items`**: partial matches due to differences in item count and order normalization.
- **Optional fields (e.g., patient_email)** were excluded from scoring since not present in the current schema.

The parser demonstrates strong structural consistency (no schema errors) but fails on date normalization and multi-item lists.

---

## 5. OpenAI vs. Minna's parser json (when available)
Only **Minna's parser** results were benchmarked.  
When OpenAI outputs become available, version `v0.2` will extend the comparison to include both parsers for relative performance.

---

## 6. Recommendations
1. **Regex Tightening**:  
   Improve date regex to capture patterns like `DD/MM/YYYY` and `Month DD, YYYY`.
2. **Numeric Normalization**:  
   Standardize rounding and currency formatting (`$430.00` → `430.00`).
3. **Line Item Matching**:  
   Use a flexible match for line items based on similar description, same code, and close amount values.
4. **Schema Audit**:  
   Add validation step to ensure all required fields (like `due_date`) are parsed before computing metrics.

---

## 7. Validation & Handoff  
The benchmark outputs were validated in Jay’s Docker notebook using validation_results_v1.1.csv.
The notebook successfully read all benchmark CSVs, confirming no missing columns and correct schema alignment.

- Validation Notes (from validation_results_v1.1.csv):

- invoice_id was missing in all 3 documents (required field).

- Several line_items[*].amount values were missing.

- One document (invoice_T1_gen3) had total_amount < subtotal_amount.

- No schema-level errors were found, confirming structural compliance.

The results verify that the benchmark outputs can be directly consumed by Jay’s validation pipeline for cross-team evaluation.

---

## 8. Next Steps
- Integrate **OpenAI parser results** for comparative benchmark.
- Expand test set beyond 3 documents.
- Add visual summary charts (precision/recall by field).
- Automate reporting in `benchmarker_v0.2`.

---

**Files Produced:**
- `bench/outputs/benchmark_v0.1.json`
- `bench/outputs/benchmark_v0.1.csv`
- `bench/outputs/metrics_by_field.csv`
- `bench/outputs/metrics_by_document.csv`

---

**Status:** Benchmark v0.1 complete and validated for Docker ingestion.
