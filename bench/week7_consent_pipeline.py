#!/usr/bin/env python
"""
week7_consent_pipeline.py

One-stop script for:
- F1 / recall / precision / accuracy
- CSV exporting
- blank field comparison
- schema validation
- duplicate detection
- determinism hashing
- week7 benchmarking report generation
"""

import json
import csv
import hashlib
import random
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

import pandas as pd

# =========================
# CONFIG
# =========================

CONFIG = {
    # TODO: set these to your actual paths
    "ground_truth_path": "bench/ground_truth_aligned_consent_v0.1.json",
    "parser_output_path": "bench/parser_output_consent_v0.1.json",
    "blank_field_log_path": "bench/blank_field_logs.json",  # from Jay

    "consent_benchmark_csv": "bench/consent_benchmark_results_v0.1.csv",
    "blank_field_report_path": "bench/blank_field_report_v0.1.json",
    "mapping_validation_log_path": "bench/outputs/mapping_validation_log.jsonl",
    "duplicate_detection_csv": "bench/outputs/duplicate_detection_summary.csv",
    "determinism_audit_log": "bench/determinism_audit_week7.jsonl",
    "week7_report_md": "reports/week7_benchmarking_report.md",

    # Critical fields for F1 thresholds
    "critical_fields": ["patient_name", "consent_type", "provider_signature"],

    # Duplicate detection similarity thresholds
    "duplicate_merge_threshold": 0.95,
    "duplicate_keep_threshold": 0.8,  # between keep & delete boundary
}

# =========================
# HELPER FUNCTIONS
# =========================


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj: Any, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def write_jsonl(records: List[Dict[str, Any]], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def sha256_of_obj(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def flatten_consent_records(
    records: Dict[str, Dict[str, Any]]
) -> List[Tuple[str, str, Any]]:
    """
    Convert {consent_id: {field: value}} -> list of (consent_id, field, value)
    """
    flattened = []
    for consent_id, fields in records.items():
        for field_name, value in fields.items():
            flattened.append((consent_id, field_name, value))
    return flattened


# =========================
# METRICS: ACCURACY / F1
# =========================

def compute_field_metrics(
    ground_truth: Dict[str, Dict[str, Any]],
    predictions: Dict[str, Dict[str, Any]],
    critical_fields: List[str],
) -> Dict[str, Any]:
    """
    Compute accuracy, precision, recall, F1 for each field + overall.
    NOTE: Here we treat "correctness" as a binary label (match vs mismatch),
    and define TP=match, FP=FN=mismatch so that F1 == accuracy.
    You can adjust this if you want a different definition.
    """

    # Accumulate stats per field
    stats = {}
    for consent_id, gt_fields in ground_truth.items():
        pred_fields = predictions.get(consent_id, {})
        for field_name, gt_val in gt_fields.items():
            pred_val = pred_fields.get(field_name, None)

            # binary correctness
            is_correct = (str(gt_val).strip() if gt_val is not None else "") == \
                         (str(pred_val).strip() if pred_val is not None else "")

            fld_stats = stats.setdefault(field_name, {"matches": 0, "total": 0})
            fld_stats["total"] += 1
            if is_correct:
                fld_stats["matches"] += 1

    # Derive metrics
    field_metrics = {}
    for field_name, s in stats.items():
        matches = s["matches"]
        total = s["total"]
        accuracy = matches / total if total > 0 else 0.0
        # F1 via symmetric TP/FP/FN
        precision = accuracy
        recall = accuracy
        f1 = accuracy  # by this convention

        field_metrics[field_name] = {
            "total": total,
            "matches": matches,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    # Overall metrics
    overall_total = sum(s["total"] for s in stats.values())
    overall_matches = sum(s["matches"] for s in stats.values())
    overall_accuracy = (
        overall_matches / overall_total if overall_total > 0 else 0.0
    )

    # Critical fields aggregate
    crit_tot = sum(stats.get(f, {}).get("total", 0) for f in critical_fields)
    crit_match = sum(stats.get(f, {}).get("matches", 0) for f in critical_fields)
    crit_acc = crit_match / crit_tot if crit_tot > 0 else 0.0

    metrics_summary = {
        "per_field": field_metrics,
        "overall": {
            "total": overall_total,
            "matches": overall_matches,
            "accuracy": overall_accuracy,
            "precision": overall_accuracy,
            "recall": overall_accuracy,
            "f1": overall_accuracy,
        },
        "critical_fields": {
            "fields": critical_fields,
            "total": crit_tot,
            "matches": crit_match,
            "accuracy": crit_acc,
            "precision": crit_acc,
            "recall": crit_acc,
            "f1": crit_acc,
        },
    }

    return metrics_summary


def export_metrics_to_csv(
    metrics_summary: Dict[str, Any],
    csv_path: str,
) -> None:
    """
    Save consent_benchmark_results_v0.1.csv in a tidy field-level format.
    """
    rows = []
    for field_name, m in metrics_summary["per_field"].items():
        rows.append(
            {
                "field": field_name,
                "total": m["total"],
                "matches": m["matches"],
                "accuracy": m["accuracy"],
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
            }
        )

    df = pd.DataFrame(rows).sort_values(by="field")
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)


# =========================
# BLANK FIELD COMPARISON
# =========================

def compare_blank_fields(
    blank_logs: List[Dict[str, Any]],
    predictions: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Compare Jay's blank/null logs against parser outputs.
    EXPECTED blank_log format per entry (you can adjust if needed):
      {
        "consent_id": "...",
        "field": "patient_middle_name",
        "reason": "missing_in_source"  # optional
      }
    """
    report = []
    for entry in blank_logs:
        consent_id = entry.get("consent_id")
        field_name = entry.get("field")
        reason = entry.get("reason", "")

        pred_fields = predictions.get(consent_id, {})
        pred_val = pred_fields.get(field_name, None)

        auto_filled = pred_val not in (None, "", "null")

        report.append(
            {
                "consent_id": consent_id,
                "field": field_name,
                "reason": reason,
                "parser_value": pred_val,
                "auto_filled": bool(auto_filled),
            }
        )

    return report


# =========================
# SCHEMA VALIDATION
# =========================

# TODO: Adjust SCHEMA_SPEC to match your real FHIR/JSON schema
# Adjusted to match the official Consent JSON schema you were given
SCHEMA_SPEC = {
    # Patient info
    "patient_name": {"type": "string"},
    "patient_first_name": {"type": ["string", "null"]},
    "patient_middle_name": {"type": ["string", "null"]},
    "patient_last_name": {"type": ["string", "null"]},
    "patient_address_name": {"type": ["string", "null"]},
    "patient_id": {"type": ["string", "null"]},
    # format: "date" → enforce YYYY-MM-DD pattern, allow null
    "patient_dob": {
        "type": ["string", "null"],
        "pattern": r"^\d{4}-\d{2}-\d{2}$",
    },
    "patient_signature": {"type": "string"},
    "patient_state": {"type": ["string", "null"]},
    "patient_city": {"type": ["string", "null"]},
    "patient_zip_code": {"type": ["string", "null"]},

    # Provider info
    "provider_name": {"type": "string"},
    "provider_address_name": {"type": "string"},
    "provider_phone": {"type": ["string", "null"]},
    "provider_fax": {"type": ["string", "null"]},
    "provider_state": {"type": "string"},
    "provider_city": {"type": "string"},
    "provider_zip_code": {"type": "string"},

    # Family / emergency contact
    "family_name": {"type": ["string", "null"]},
    "family_relation": {"type": ["string", "null"]},
    "family_phone": {"type": ["string", "null"]},
    "family_address_name": {"type": ["string", "null"]},
    "family_state": {"type": ["string", "null"]},
    "family_city": {"type": ["string", "null"]},
    "family_zip_code": {"type": ["string", "null"]},

    # Guardian
    "guardian_name": {"type": ["string", "null"]},
    "guardian_signature": {"type": ["string", "null"]},
    "guardian_relation": {"type": ["string", "null"]},

    # Dates & expiration
    "date": {
        "type": "string",
        "pattern": r"^\d{4}-\d{2}-\d{2}$",
    },
    "expiration_date": {
        "type": ["string", "null"],
        "pattern": r"^\d{4}-\d{2}-\d{2}$",
    },
    "expiration_event": {"type": ["string", "null"]},

    # Translator
    "translator_name": {"type": ["string", "null"]},
    "translator_signature": {"type": ["string", "null"]},

}


def is_type_valid(value: Any, expected_type) -> bool:
    if isinstance(expected_type, list):
        return any(is_type_valid(value, t) for t in expected_type)

    if expected_type == "string":
        return value is None or isinstance(value, str)
    if expected_type == "null":
        return value is None
    if expected_type == "integer":
        return value is None or isinstance(value, int)
    if expected_type == "number":
        return value is None or isinstance(value, (int, float))
    if expected_type == "boolean":
        return value is None or isinstance(value, bool)

    # default: accept
    return True


def validate_schema_and_mapping(
    predictions: Dict[str, Dict[str, Any]],
    schema_spec: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validate parser outputs against schema types and patterns.
    Returns:
      - list of mapping drift / format errors
      - summary dict with validation rate
    """
    errors = []
    total_fields = 0
    valid_fields = 0

    for consent_id, fields in predictions.items():
        for field_name, value in fields.items():
            total_fields += 1

            spec = schema_spec.get(field_name)
            if spec is None:
                # unmapped / extra field
                errors.append(
                    {
                        "consent_id": consent_id,
                        "field": field_name,
                        "value": value,
                        "error_type": "mapping_drift",
                        "message": "Field not defined in schema",
                    }
                )
                continue

            # Type check
            expected_type = spec.get("type")
            type_ok = is_type_valid(value, expected_type)

            # Pattern check
            pattern = spec.get("pattern")
            pattern_ok = True
            if pattern and value not in (None, ""):
                pattern_ok = bool(re.fullmatch(pattern, str(value)))

            if type_ok and pattern_ok:
                valid_fields += 1
            else:
                err_msg = []
                if not type_ok:
                    err_msg.append(f"Expected type {expected_type}")
                if not pattern_ok:
                    err_msg.append(f"Value does not match pattern {pattern}")
                errors.append(
                    {
                        "consent_id": consent_id,
                        "field": field_name,
                        "value": value,
                        "error_type": "format_error",
                        "message": "; ".join(err_msg),
                    }
                )

    validation_rate = (
        valid_fields / total_fields if total_fields > 0 else 0.0
    )
    summary = {
        "total_fields": total_fields,
        "valid_fields": valid_fields,
        "invalid_fields": total_fields - valid_fields,
        "validation_rate": validation_rate,
    }

    return errors, summary


# =========================
# DUPLICATE DETECTION
# =========================

def concat_record_text(record: Dict[str, Any]) -> str:
    return " | ".join(f"{k}:{v}" for k, v in sorted(record.items()))


def similarity_ratio(a: str, b: str) -> float:
    # Simple character-level similarity (no extra deps)
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a, b).ratio()


def simulate_duplicate_records(
    records: Dict[str, Dict[str, Any]],
    n_dups: int = 5,
) -> Dict[str, Dict[str, Any]]:
    """
    Deterministic simulation of duplicates by slightly perturbing some fields.
    """
    random.seed(42)
    consent_ids = list(records.keys())
    if not consent_ids:
        return records

    dup_records = dict(records)  # shallow copy

    for i in range(min(n_dups, len(consent_ids))):
        cid = random.choice(consent_ids)
        original = records[cid]

        new_id = f"{cid}_dup{i+1}"
        new_rec = dict(original)

        # Slight perturbation: add a trailing space or minor text tweak
        for field_name, value in new_rec.items():
            if isinstance(value, str) and value:
                new_rec[field_name] = value + " "
                break  # just perturb one field

        dup_records[new_id] = new_rec

    return dup_records


def run_duplicate_detection(
    records: Dict[str, Dict[str, Any]],
    merge_threshold: float,
    keep_threshold: float,
) -> List[Dict[str, Any]]:
    """
    Pairwise duplicate detection between original and simulated duplicate records.
    Decision logic:
      - similarity >= merge_threshold → merge
      - keep_threshold <= similarity < merge_threshold → keep
      - similarity < keep_threshold → delete
    """
    rows = []

    keys = sorted(records.keys())
    for k in keys:
        if "_dup" not in k:
            continue  # only evaluate original vs duplicates

        # Infer original id before "_dup"
        orig = k.split("_dup")[0]
        if orig not in records:
            continue

        rec_orig = records[orig]
        rec_dup = records[k]

        s_orig = concat_record_text(rec_orig)
        s_dup = concat_record_text(rec_dup)

        sim = similarity_ratio(s_orig, s_dup)

        if sim >= merge_threshold:
            decision = "merge"
        elif sim >= keep_threshold:
            decision = "keep"
        else:
            decision = "delete"

        rows.append(
            {
                "original_consent_id": orig,
                "duplicate_consent_id": k,
                "similarity_score": sim,
                "decision": decision,
            }
        )

    return rows


def export_duplicate_detection_csv(
    rows: List[Dict[str, Any]],
    csv_path: str,
) -> None:
    df = pd.DataFrame(rows)
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)


# =========================
# DETERMINISM AUDIT
# =========================

def run_full_metrics_once(
    ground_truth: Dict[str, Dict[str, Any]],
    predictions: Dict[str, Dict[str, Any]],
    blank_logs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Execute all metric/log-producing steps and return a single dict
    that we can hash for determinism.
    (Doesn't write files; just returns structured results.)
    """
    metrics_summary = compute_field_metrics(
        ground_truth,
        predictions,
        critical_fields=CONFIG["critical_fields"],
    )

    blank_report = compare_blank_fields(blank_logs, predictions)

    schema_errors, schema_summary = validate_schema_and_mapping(
        predictions,
        schema_spec=SCHEMA_SPEC,
    )

    simulated_records = simulate_duplicate_records(predictions)
    dup_rows = run_duplicate_detection(
        simulated_records,
        merge_threshold=CONFIG["duplicate_merge_threshold"],
        keep_threshold=CONFIG["duplicate_keep_threshold"],
    )

    # Return everything in a deterministic structure
    return {
        "metrics_summary": metrics_summary,
        "blank_report": blank_report,
        "schema_summary": schema_summary,
        "schema_errors": schema_errors,
        "duplicate_rows": dup_rows,
    }


def run_determinism_audit(
    ground_truth: Dict[str, Dict[str, Any]],
    predictions: Dict[str, Dict[str, Any]],
    blank_logs: List[Dict[str, Any]],
    audit_log_path: str,
) -> Dict[str, Any]:
    """
    Rerun full metrics twice; confirm bit-identical hashes.
    Write determinism_audit_week7.jsonl.
    """
    run1 = run_full_metrics_once(ground_truth, predictions, blank_logs)
    run2 = run_full_metrics_once(ground_truth, predictions, blank_logs)

    hash1 = sha256_of_obj(run1)
    hash2 = sha256_of_obj(run2)
    deterministic = (hash1 == hash2)

    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hash_run1": hash1,
        "hash_run2": hash2,
        "deterministic": deterministic,
    }

    # Append to JSONL
    Path(audit_log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")

    return record


# =========================
# HYBRID K SUMMARY (from k-hybrid consent test)
# =========================

def get_hybrid_summary() -> Dict[str, Any]:
    """
    Hybrid k-test results from the consent QA run.

    These values came from your k-hybrid notebook output:
      - Hybrid QA Score: 0.944 → 94.37%
      - Micro P/R/F1: 0.9843 / 0.9488 / 0.9662
      - Critical fields avg F1: 0.7500

    You can later replace these literals by parsing the CSVs directly
    if you want it fully automated.
    """
    return {
        "hybrid_qa_score": 0.944,       # k-hybrid scalar score
        "hybrid_qa_percent": 94.37,     # human-readable %
        "micro_precision": 0.9843,
        "micro_recall": 0.9488,
        "micro_f1": 0.9662,
        "critical_avg_f1": 0.7500,
        # thresholds for interpretation
        "threshold_hybrid_k": 0.85,
        "threshold_critical_f1": 0.95,
    }


# =========================
# WEEK 7 REPORT GENERATION
# =========================

def generate_week7_report(
    metrics_summary: Dict[str, Any],
    schema_summary: Dict[str, Any],
    blank_report: List[Dict[str, Any]],
    dup_rows: List[Dict[str, Any]],
    determinism_record: Dict[str, Any],
    hybrid_summary: Dict[str, Any],
    report_path: str,
) -> None:
    crit = metrics_summary["critical_fields"]
    overall = metrics_summary["overall"]
    num_blank = len(blank_report)
    num_dup = len(dup_rows)
    h = hybrid_summary

    md = []
    md.append("# Week 7 Benchmarking Report v2.0\n")

    # --- Hybrid k Consent QA Summary ---
    md.append("## 0. Hybrid k Consent QA Summary\n")
    md.append(
        f"- Hybrid QA Score (k): **{h['hybrid_qa_score']:.4f}** "
        f"→ **{h['hybrid_qa_percent']:.2f}%**\n"
    )
    md.append(
        f"- Micro Precision / Recall / F1: "
        f"**{h['micro_precision']:.4f}** / "
        f"**{h['micro_recall']:.4f}** / "
        f"**{h['micro_f1']:.4f}**\n"
    )
    md.append(f"- Critical fields avg F1: **{h['critical_avg_f1']:.4f}**\n")
    md.append(
        f"- Target thresholds: "
        f"k ≥ **{h['threshold_hybrid_k']:.2f}**, "
        f"critical F1 ≥ **{h['threshold_critical_f1']:.2f}**\n"
    )

    status_k = (
        "Met" if h["hybrid_qa_score"] >= h["threshold_hybrid_k"] else "⚠️ Below target"
    )
    status_crit = (
        "Met"
        if h["critical_avg_f1"] >= h["threshold_critical_f1"]
        else "Below target"
    )

    md.append(f"- Status (Hybrid k): {status_k}\n")
    md.append(f"- Status (Critical fields F1): {status_crit}\n")

    md.append("\n---\n")

    # --- Existing sections ---
    md.append("## 1. Consent Benchmark Summary\n")
    md.append("### 1.1 Overall Metrics\n")
    md.append(f"- Total fields: **{overall['total']}**\n")
    md.append(f"- Matches: **{overall['matches']}**\n")
    md.append(f"- Accuracy / F1: **{overall['f1']:.4f}**\n")

    md.append("\n### 1.2 Critical Fields (Hybrid k Proxy via F1)\n")
    md.append(f"- Fields: `{', '.join(crit['fields'])}`\n")
    md.append(f"- Total: **{crit['total']}**\n")
    md.append(f"- Matches: **{crit['matches']}**\n")
    md.append(f"- F1 (approx.): **{crit['f1']:.4f}**\n")

    md.append("\n## 2. Blank Field & Mapping Validation Analysis\n")
    md.append(f"- Blank field entries reviewed: **{num_blank}**\n")

    auto_filled = sum(1 for r in blank_report if r["auto_filled"])
    md.append(f"- Auto-filled blank fields: **{auto_filled}**\n")

    md.append("\n### 2.1 Schema Validation\n")
    md.append(
        f"- Total fields validated: **{schema_summary['total_fields']}**\n"
    )
    md.append(
        f"- Valid fields: **{schema_summary['valid_fields']}**\n"
    )
    md.append(
        f"- Invalid fields: **{schema_summary['invalid_fields']}**\n"
    )
    md.append(
        f"- Validation rate: **{schema_summary['validation_rate']:.4f}**\n"
    )

    md.append("\n## 3. Duplicate Record Trial Summary\n")
    md.append(f"- Duplicate pairs evaluated: **{num_dup}**\n")

    if num_dup > 0:
        decisions = pd.DataFrame(dup_rows)["decision"].value_counts().to_dict()
        for d, c in decisions.items():
            md.append(f"- `{d}`: **{c}**\n")

    md.append("\n## 4. Determinism Verification Results\n")
    md.append(
        f"- Deterministic: **{determinism_record['deterministic']}**\n"
    )
    md.append(f"- Hash run1: `{determinism_record['hash_run1']}`\n")
    md.append(f"- Hash run2: `{determinism_record['hash_run2']}`\n")

    md.append("\n## 5. Recommendations\n")
    md.append("### 5.1 For Minna (Parser)\n")
    md.append("- Review fields with repeated mapping or format errors.\n")
    md.append("- Prioritize critical fields where F1 < target threshold.\n")
    md.append("- Investigate over/under-filling of blank fields.\n")

    md.append("\n### 5.2 For Jay (Validation)\n")
    md.append("- Confirm schema assumptions for fields with high invalid rate.\n")
    md.append("- Align blank field rules with parser auto-fill logic.\n")
    md.append("- Define explicit handling for borderline duplicate cases.\n")

    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


# =========================
# MAIN ORCHESTRATION
# =========================

def main():
    cfg = CONFIG

    # ---- Load data ----
    ground_truth_raw = load_json(cfg["ground_truth_path"])
    parser_output_raw = load_json(cfg["parser_output_path"])
    blank_logs_raw = load_json(cfg["blank_field_log_path"])

    # =========================
    # Normalize GROUND TRUTH
    # expected final shape:
    #   { "consent_T1_gen1": {field: value, ...}, ... }
    # =========================
    if isinstance(ground_truth_raw, dict) and "docs" in ground_truth_raw:
        docs = ground_truth_raw["docs"]
        ground_truth = {}

        for doc in docs:
            # consent id is stored in "document_id"
            consent_id = doc.get("document_id")
            if not consent_id:
                continue

            # actual fields live under "data"
            fields = doc.get("data") or {}

            ground_truth[consent_id] = fields
    else:
        # Already in the correct format
        ground_truth = ground_truth_raw

    # Debug (optional)
    print("DEBUG ground_truth size:", len(ground_truth))
    if ground_truth:
        sample_key = list(ground_truth.keys())[0]
        print("DEBUG sample GT id:", sample_key)
        print("DEBUG sample GT fields:", list(ground_truth[sample_key].keys())[:10])

    # =========================
    # Normalize PARSER OUTPUTS
    # also want: {consent_id: {field: value}}
    # if your merged parser_output has the same "data" structure, strip it too
    # =========================
    if isinstance(parser_output_raw, dict):
        preds = {}
        for consent_id, rec in parser_output_raw.items():
            if isinstance(rec, dict) and "data" in rec:
                preds[consent_id] = rec["data"]
            else:
                preds[consent_id] = rec
        predictions = preds
    else:
        predictions = parser_output_raw

    # Debug (optional)
    print("DEBUG predictions size:", len(predictions))
    if predictions:
        sample_key = list(predictions.keys())[0]
        print("DEBUG sample PRED id:", sample_key)
        print("DEBUG sample PRED fields:", list(predictions[sample_key].keys())[:10])

    # Blank logs should be a list (or an empty list)
    blank_logs = blank_logs_raw or []

    # ---- Metrics + CSV ----
    metrics_summary = compute_field_metrics(
        ground_truth,
        predictions,
        cfg["critical_fields"],
    )
    export_metrics_to_csv(metrics_summary, cfg["consent_benchmark_csv"])

    # ---- Blank field report ----
    blank_report = compare_blank_fields(blank_logs, predictions)
    save_json(blank_report, cfg["blank_field_report_path"])

    # ---- Schema validation ----
    schema_errors, schema_summary = validate_schema_and_mapping(
        predictions,
        SCHEMA_SPEC,
    )
    write_jsonl(schema_errors, cfg["mapping_validation_log_path"])

    # ---- Duplicate detection ----
    simulated_records = simulate_duplicate_records(predictions)
    dup_rows = run_duplicate_detection(
        simulated_records,
        merge_threshold=cfg["duplicate_merge_threshold"],
        keep_threshold=cfg["duplicate_keep_threshold"],
    )
    export_duplicate_detection_csv(dup_rows, cfg["duplicate_detection_csv"])

    # ---- Determinism hashing ----
    determinism_record = run_determinism_audit(
        ground_truth,
        predictions,
        blank_logs,
        cfg["determinism_audit_log"],
    )

    # ---- Hybrid k summary (from your k-hybrid consent test) ----
    hybrid_summary = get_hybrid_summary()

    # ---- Week 7 report ----
    generate_week7_report(
        metrics_summary=metrics_summary,
        schema_summary=schema_summary,
        blank_report=blank_report,
        dup_rows=dup_rows,
        determinism_record=determinism_record,
        hybrid_summary=hybrid_summary,
        report_path=cfg["week7_report_md"],
    )

    print("Week 7 consent pipeline completed.")
    print(f"- Bench CSV: {cfg['consent_benchmark_csv']}")
    print(f"- Blank field report: {cfg['blank_field_report_path']}")
    print(f"- Mapping validation log: {cfg['mapping_validation_log_path']}")
    print(f"- Duplicate detection CSV: {cfg['duplicate_detection_csv']}")
    print(f"- Determinism audit: {cfg['determinism_audit_log']}")
    print(f"- Week 7 report: {cfg['week7_report_md']}")


if __name__ == "__main__":
    main()
