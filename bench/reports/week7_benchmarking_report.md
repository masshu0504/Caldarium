# Week 7 Benchmarking Report v2.0 (Draft)

**Date:** 2025-11-07

## 1) Progress Summary
- Schema & format validation completed on consent outputs
- Duplicate detection run and logged
- Blocked: Benchmarking (Hybrid-k, F1/Recall/Precision) — awaiting ground truth + Minna’s parser JSONs
- Blocked: Blank field analysis — awaiting Jay’s validation logs
- Blocked: API audit — awaiting Matthew Oh’s logs

## 2) Schema Validation
- Validation Rate: (paste the printed %)
- Log: `bench/outputs/mapping_validation_log.jsonl`

## 3) Duplicate Detection
- File: `bench/outputs/duplicate_detection_summary.csv`
- Threshold: 0.92
- Summary: (paste merge/keep counts)

## 4) Dashboard
- `bench/dashboard/dashboard_v0.1.csv` (currently shows validation issue count)

## 5) Next Actions
- Ingest GT + Minna outputs → run F1 & hybrid-k
- Ingest Jay’s logs → produce blank_field_report_v0.1.json
- Add metrics to dashboard and finalize report
