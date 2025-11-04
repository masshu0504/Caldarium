#!/usr/bin/env python3
"""
Benchmarker Module v0.1 (Final with Audit Logging)
=================================================

Compares Minna parser JSON outputs against Ground Truth JSONs across documents.
Computes per-field Precision, Recall, F1, and overall accuracy.
Saves results to JSON & CSV with environment details, reproducibility metadata,
and aggregated metrics for validation (Jay’s notebook compatible).
"""

import pandas as pd
import json
import numpy as np
import sys
import hashlib
import platform
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import warnings
import random
import uuid
import subprocess
import re

warnings.filterwarnings("ignore")

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------------------
# Utility: git commit short hash
# ------------------------------------------------------------------------------

def _git_commit_short(root: Path) -> str:
    try:
        rev = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return rev.decode().strip()
    except Exception:
        return "nogit"


# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------

class BenchmarkConfig:
    """Configuration class for benchmark parameters"""

    def __init__(self):
        self.version = "v0.1"

        # Root folders
        #self.gt_root = HERE.parent / "PDFLogicCode" / "archives"
        self.ground_truth_dir = HERE.parent / "PDFLogicCode" / "archives" / "Oct28#3"
        self.parser_dir = HERE.parent / "parser_json_output"
        self.output_dir = HERE / "outputs"

        # Choose the newest archive that contains invoice_*.json
        #self.ground_truth_dir = self._locate_latest_gt_dir()

        # Auto-detect overlapping documents
        self.test_documents: Optional[List[str]] = None
        self.parser_suffix = "_regex.json"

        # Keep this list for reporting (schema compliance), but metrics will
        # evaluate ALL fields found across files.
        self.fields_to_evaluate = [
            "invoice_number", "due_date", "patient_name",
            "subtotal_amount", "invoice_date", "total_amount", "line_items",
        ]

    def _locate_latest_gt_dir(self) -> Path:
        if not self.gt_root.exists():
            raise FileNotFoundError(f"Ground-truth root not found: {self.gt_root}")
        candidates = [p for p in self.gt_root.iterdir() if p.is_dir()]
        if not candidates:
            raise FileNotFoundError(f"No archive folders found under: {self.gt_root}")
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for d in candidates:
            if list(d.glob("invoice_*.json")):
                print(f"Using ground truth archive: {d}")
                return d
        # fallback to the most recent even if it doesn't have files (unlikely)
        return candidates[0]


# ------------------------------------------------------------------------------
# Fallback Audit Logger
# ------------------------------------------------------------------------------

class _CSVShimAuditLogger:
    """Fallback logger that appends CSV rows to outputs/audit_log.csv"""
    def __init__(self, out_dir: Path):
        self.path = out_dir / "audit_log.csv"
        self._header_written = self.path.exists()

    def log(self, row: dict):
        import csv
        keys = [
            "timestamp", "run_id", "schema_version", "git", "stage",
            "field", "document", "precision", "recall", "f1",
            "gt_present", "parser_present", "matches", "total_documents",
            "match", "match_type"
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            if not self._header_written:
                w.writeheader()
                self._header_written = True
            row_out = {k: row.get(k, "") for k in keys}
            w.writerow(row_out)


def get_audit_logger(out_dir: Path):
    """Try importing audit_logger; fallback to CSV shim.
    Supports:
      - logger.log(record)
      - logger.logs(record)  [callable]
      - logger.logs.append(record)  [list-like]
    """
    try:
        from audit_logger import AuditLogger  # noqa
        logger = AuditLogger(out_dir)

        # Case 1: .log(record) exists
        if hasattr(logger, "log") and callable(getattr(logger, "log")):
            return logger

        # Case 2/3: .logs exists (callable or list-like)
        if hasattr(logger, "logs"):
            logs_attr = getattr(logger, "logs")

            # 2a) .logs(record) is callable
            if callable(logs_attr):
                class _CompatLogger:
                    def __init__(self, inner): self.inner = inner
                    def log(self, record): self.inner.logs(record)
                return _CompatLogger(logger)

            # 2b) .logs is a list-like; append records
            if isinstance(logs_attr, list):
                class _CompatListLogger:
                    def __init__(self, inner): self.inner = inner
                    def log(self, record): self.inner.logs.append(record)
                return _CompatListLogger(logger)

        # Fallback
        return _CSVShimAuditLogger(out_dir)

    except Exception:
        return _CSVShimAuditLogger(out_dir)


# ------------------------------------------------------------------------------
# Field comparator
# ------------------------------------------------------------------------------

class FieldComparator:
    """Compare and normalize field values."""

    @staticmethod
    def normalize_value(value):
        if pd.isna(value) or value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower()
        return str(value).strip().lower()

    @staticmethod
    def _normalize_date_like(s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        s = str(s).strip()
        if not s:
            return None
        fmts = ["%Y-%m-%d", "%Y/%m/%d", "%m-%d-%Y", "%m/%d/%Y"]
        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y%m%d")
            except Exception:
                pass
        digits = re.sub(r"\D", "", s)
        return digits if len(digits) == 8 else s

    @staticmethod
    def compare_scalar_field(gt_value, parser_value, field_name):
        gt_norm = FieldComparator.normalize_value(gt_value)
        parser_norm = FieldComparator.normalize_value(parser_value)

        if gt_norm is None and parser_norm is None:
            return True, "both_missing"
        if gt_norm is None:
            return False, "gt_missing"
        if parser_norm is None:
            return False, "parser_missing"

        if gt_norm == parser_norm:
            return True, "exact_match"

        numeric_fields = ['subtotal_amount', 'total_amount', 'discount_amount', 'patient_age']
        if field_name in numeric_fields:
            try:
                gt_num = float(str(gt_value).replace('$', '').replace(',', ''))
                parser_num = float(str(parser_value).replace('$', '').replace(',', ''))
                if abs(gt_num - parser_num) < 0.01:
                    return True, "numeric_match"
            except Exception:
                pass

        date_fields = ['invoice_date', 'due_date', 'admission_date', 'discharge_date']
        if field_name in date_fields:
            gt_date = FieldComparator._normalize_date_like(gt_value)
            pr_date = FieldComparator._normalize_date_like(parser_value)
            if gt_date is None and pr_date is None:
                return True, "both_missing"
            if gt_date is None:
                return False, "gt_missing"
            if pr_date is None:
                return False, "parser_missing"
            if gt_date == pr_date:
                return True, "date_match"
            
        # Handle phone numbers more flexibly (normalize to 10 digits)
        if "phone" in field_name:
            def normalize_phone(p):
                if p is None:
                    return ""
                p = str(p)
                digits = re.sub(r"\D", "", p)  # keep digits only
                # Strip leading US country code '1' if present (11 -> 10)
                if len(digits) == 11 and digits.startswith("1"):
                    digits = digits[1:]
                return digits

            gt_phone = normalize_phone(gt_value)
            pr_phone = normalize_phone(parser_value)
            if gt_phone and pr_phone and gt_phone == pr_phone:
                return True, "phone_match"
            
        # Handle addresses: ignore case, whitespace, punctuation
        if "address" in field_name:
            def normalize_address(s):
                if not s:
                    return ""
                s = str(s).lower()
                # remove everything except a-z and digits
                s = re.sub(r"[^a-z0-9]", "", s)
                return s

            gt_addr = normalize_address(gt_value)
            pr_addr = normalize_address(parser_value)
            if gt_addr and pr_addr and gt_addr == pr_addr:
                return True, "address_match"

        return False, "mismatch"

    @staticmethod
    def compare_line_items(gt_items, parser_items):
        """Compare arrays of line items by (code, amount) with relaxed description matching."""
        if not gt_items and not parser_items:
            return True, "both_empty"
        if not gt_items:
            return False, "gt_empty"
        if not parser_items:
            return False, "parser_empty"

        def normalize_items(items):
            normalized = []
            for item in items:
                if isinstance(item, dict):
                    try:
                        amt = float(str(item.get("amount", "")).replace("$", "").replace(",", ""))
                    except Exception:
                        amt = 0.0
                    normalized.append({
                        "code": FieldComparator.normalize_value(item.get("code", "")),
                        "description": FieldComparator.normalize_value(item.get("description", "")),
                        "amount": amt
                    })
            return normalized

        gt_norm = normalize_items(gt_items)
        pr_norm = normalize_items(parser_items)

        # Match by (code, amount)
        from collections import Counter
        gt_keys = [(g["code"], g["amount"]) for g in gt_norm]
        pr_keys = [(p["code"], p["amount"]) for p in pr_norm]
        hard = sum((Counter(gt_keys) & Counter(pr_keys)).values())

        if hard == len(gt_norm) == len(pr_norm):
            return True, "exact_match_by_code_amount"

        if len(gt_norm) != len(pr_norm):
            return False, f"length_mismatch_{len(gt_norm)}_vs_{len(pr_norm)}"

        return False, f"partial_match_{hard}/{len(gt_norm)}"


# ------------------------------------------------------------------------------
# Benchmark Runner
# ------------------------------------------------------------------------------

class BenchmarkRunner:
    """Main benchmark process"""

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.ground_truth = {}
        self.parser_results = {}
        self.field_metrics = {}
        self.environment_details = {}

        # Run/session identity
        self.run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self.schema_version = self.config.version
        self.git_short = _git_commit_short(HERE.parent)
        self.logger = get_audit_logger(self.config.output_dir)

    # ---------------- Helpers ---------------- #

    def _has_value(self, v) -> bool:
        if v is None:
            return False
        if isinstance(v, (list, tuple, dict)):
            return len(v) > 0
        if isinstance(v, (np.ndarray, pd.Series)):
            return v.size > 0
        try:
            if isinstance(v, float) and np.isnan(v):
                return False
        except Exception:
            pass
        return str(v).strip() != ''

    def _discover_test_documents(self, limit: Optional[int] = None) -> List[str]:
        parser_docs = set()
        # parser files look like: invoice_T1_gen1_regex.json
        for p in self.config.parser_dir.glob(f"*{self.config.parser_suffix}"):
            name = p.name[:-len(self.config.parser_suffix)]  # "invoice_T1_gen1"
            if name.startswith("invoice_"):
                name = name[len("invoice_"):]                 # "T1_gen1"
            if name:
                parser_docs.add(name)

        gt_docs = set()
        for p in self.config.ground_truth_dir.glob("invoice_*.json"):
            doc = p.stem[len("invoice_"):]                    # "T1_gen1"
            if doc:
                gt_docs.add(doc)

        overlap = sorted(parser_docs & gt_docs)
        print("Overlapping documents:", overlap)
        if limit:
            overlap = overlap[:limit]
        return overlap

    # ---------------- Loaders ---------------- #

    def load_ground_truth(self):
        print("Loading ground truth JSON files...")
        gt = {}
        for doc in self.config.test_documents:
            fname = f"invoice_{doc}.json"
            path = self.config.ground_truth_dir / fname
            try:
                with open(path, "r", encoding="utf-8") as f:
                    gt[doc] = json.load(f)
                print(f"✓ Loaded ground truth: {fname}")
            except Exception as e:
                print(f"✗ Could not load {path}: {e}")
        print(f"Ground truth loaded for {len(gt)} documents")
        self.ground_truth = gt
        return gt

    def load_parser_results(self):
        print("Loading parser JSON files...")
        pr = {}
        for doc in self.config.test_documents:
            fname = f"invoice_{doc}{self.config.parser_suffix}"
            path = self.config.parser_dir / fname
            try:
                with open(path, "r", encoding="utf-8") as f:
                    pr[doc] = json.load(f)
                print(f"✓ Loaded parser: {fname}")
            except Exception as e:
                print(f"✗ Could not load {path}: {e}")
        print(f"Parser results loaded for {len(pr)} documents")
        self.parser_results = pr
        return pr

    # ---------------- Environment ---------------- #

    def record_environment_details(self):
        print("Recording environment details...")
        details = {
            "benchmark_version": self.config.version,
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "pandas_version": pd.__version__,
            "numpy_version": np.__version__,
            "platform": platform.platform(),
            "random_seed": RANDOM_SEED,
            "git_commit": self.git_short,
            "run_id": self.run_id,
            "test_documents": self.config.test_documents,
            "data_hashes": {}
        }

        for doc in self.config.test_documents:
            gt_path = self.config.ground_truth_dir / f"invoice_{doc}.json"
            pr_path = self.config.parser_dir / f"invoice_{doc}{self.config.parser_suffix}"
            details["data_hashes"][f"gt:{doc}"] = self._file_hash(gt_path)
            details["data_hashes"][f"parser:{doc}"] = self._file_hash(pr_path)

        self.environment_details = details
        return details

    def _file_hash(self, path: Path) -> str:
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except FileNotFoundError:
            return "file_not_found"

    # ---------------- Schema Compliance & Diagnostics ---------------- #

    def verify_schema_compliance(self) -> Dict[str, Any]:
        """Report required-field presence for GT and Parser per document."""
        required = set(self.config.fields_to_evaluate)
        report = {"by_document": {}, "missing_in_gt_counts": {}, "missing_in_parser_counts": {}}

        for doc in self.config.test_documents:
            gt = self.ground_truth.get(doc, {})
            pr = self.parser_results.get(doc, {})
            miss_gt, miss_pr = [], []
            for f in required:
                if not self._has_value(gt.get(f)):
                    miss_gt.append(f)
                    report["missing_in_gt_counts"][f] = report["missing_in_gt_counts"].get(f, 0) + 1
                if not self._has_value(pr.get(f)):
                    miss_pr.append(f)
                    report["missing_in_parser_counts"][f] = report["missing_in_parser_counts"].get(f, 0) + 1
            report["by_document"][doc] = {
                "missing_in_gt": sorted(miss_gt),
                "missing_in_parser": sorted(miss_pr),
            }
        return report

    def build_diagnostics(self) -> Dict[str, Any]:
        """Summarize missing fields, partial matches, date matches, and numeric discrepancies."""
        numeric_fields = {"subtotal_amount", "total_amount", "discount_amount", "patient_age"}
        diags = {
            "missing_fields_per_parser": {},   # field -> count of parser_missing
            "partial_matches": [],             # list of {field, document, match_type}
            "date_format_matches": [],         # where match_type == date_match
            "numeric_discrepancies": []        # numeric fields present on both but mismatch
        }

        for field, m in self.field_metrics.items():
            for r in m["document_results"]:
                mt = r["match_type"]
                doc = r["document"]
                gt_has = self._has_value(r["gt_value"])
                pr_has = self._has_value(r["parser_value"])

                if mt == "parser_missing":
                    diags["missing_fields_per_parser"][field] = diags["missing_fields_per_parser"].get(field, 0) + 1

                if isinstance(mt, str) and (mt.startswith("partial_match") or mt.startswith("length_mismatch")):
                    diags["partial_matches"].append({"field": field, "document": doc, "match_type": mt})

                if mt == "date_match":
                    diags["date_format_matches"].append({"field": field, "document": doc})

                if field in numeric_fields and gt_has and pr_has and not r["match"]:
                    diags["numeric_discrepancies"].append({
                        "field": field, "document": doc,
                        "gt_value": r["gt_value"], "parser_value": r["parser_value"]
                    })

        return diags

    # ---------------- Metrics ---------------- #

    def compute_field_metrics(self, field_name: str):
        results = {
            "field": field_name,
            "total_documents": len(self.config.test_documents),
            "gt_present": 0,
            "parser_present": 0,
            "both_present": 0,
            "matches": 0,
            "document_results": []
        }

        for doc in self.config.test_documents:
            if doc not in self.ground_truth or doc not in self.parser_results:
                continue

            gt_value = self.ground_truth[doc].get(field_name)
            pr_value = self.parser_results[doc].get(field_name)

            gt_has = self._has_value(gt_value)
            pr_has = self._has_value(pr_value)

            if gt_has:
                results["gt_present"] += 1
            if pr_has:
                results["parser_present"] += 1
            if gt_has and pr_has:
                results["both_present"] += 1

            if field_name == "line_items":
                is_match, mtype = FieldComparator.compare_line_items(gt_value, pr_value)
            else:
                is_match, mtype = FieldComparator.compare_scalar_field(gt_value, pr_value, field_name)

            #if is_match:
               # results["matches"] += 1
            # AFTER: only count when both present
            if is_match and gt_has and pr_has:
                results["matches"] += 1

            results["document_results"].append({
                "document": doc,
                "gt_value": gt_value,
                "parser_value": pr_value,
                "match": is_match,
                "match_type": mtype
            })

        # Avoid penalizing fields missing on both sides
        if results["gt_present"] == 0 and results["parser_present"] == 0:
            results.update({"precision": None, "recall": None, "f1_score": None})
        else:
            prec = results["matches"] / results["parser_present"] if results["parser_present"] else 0.0
            rec = results["matches"] / results["gt_present"] if results["gt_present"] else 0.0
            f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) else 0.0
            results.update({"precision": prec, "recall": rec, "f1_score": f1})

        return results

    def compute_all_field_metrics(self):
        print("Computing metrics for all fields...")

        # Union of keys seen in any GT or parser document
        union_fields = set()
        for doc in self.config.test_documents:
            union_fields.update(self.ground_truth.get(doc, {}).keys())
            union_fields.update(self.parser_results.get(doc, {}).keys())

        # Ensure our “required” list is included
        union_fields.update(self.config.fields_to_evaluate)

        # Put line_items last for nicer output
        ordered = sorted(f for f in union_fields if f != "line_items")
        if "line_items" in union_fields:
            ordered.append("line_items")

        metrics = {}
        for f in ordered:
            print(f"Computing metrics for field: {f}")
            metrics[f] = self.compute_field_metrics(f)
        self.field_metrics = metrics
        return metrics

    def compute_overall_accuracy(self):
        comparable = sum(m["both_present"] for m in self.field_metrics.values())
        matches = sum(m["matches"] for m in self.field_metrics.values())
        return matches / comparable if comparable else 0.0

    # ---------------- Logging & Exports ---------------- #

    def _log_per_field_metrics(self):
        ts = datetime.now().isoformat()
        for field, m in self.field_metrics.items():
            self.logger.log({
                "timestamp": ts,
                "run_id": self.run_id,
                "schema_version": self.schema_version,
                "git": self.git_short,
                "stage": "metrics_by_field",
                "field": field,
                "document": "",
                "precision": m["precision"] if m["precision"] is not None else "",
                "recall": m["recall"] if m["recall"] is not None else "",
                "f1": m["f1_score"] if m["f1_score"] is not None else "",
                "gt_present": m["gt_present"],
                "parser_present": m["parser_present"],
                "matches": m["matches"],
                "total_documents": m["total_documents"],
                "match": "",
                "match_type": ""
            })

    def _log_per_document_metrics(self):
        ts = datetime.now().isoformat()
        for field, m in self.field_metrics.items():
            for r in m["document_results"]:
                self.logger.log({
                    "timestamp": ts,
                    "run_id": self.run_id,
                    "schema_version": self.schema_version,
                    "git": self.git_short,
                    "stage": "metrics_by_document",
                    "field": field,
                    "document": r["document"],
                    "precision": "",
                    "recall": "",
                    "f1": "",
                    "gt_present": int(self._has_value(r["gt_value"])),
                    "parser_present": int(self._has_value(r["parser_value"])),
                    "matches": "",
                    "total_documents": "",
                    "match": r["match"],
                    "match_type": r["match_type"]
                })

    def export_metrics_by_field(self) -> Path:
        rows = []
        for field, m in self.field_metrics.items():
            rows.append({
                "run_id": self.run_id,
                "schema_version": self.schema_version,
                "git": self.git_short,
                "field": field,
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1_score"],
                "gt_present": m["gt_present"],
                "parser_present": m["parser_present"],
                "matches": m["matches"],
                "total_documents": m["total_documents"],
            })
        df = pd.DataFrame(rows, columns=[
            "run_id","schema_version","git",
            "field","precision","recall","f1",
            "gt_present","parser_present","matches","total_documents"
        ])
        out = Path(self.config.output_dir) / "metrics_by_field.csv"
        df.to_csv(out, index=False)
        return out

    def export_metrics_by_document(self) -> Path:
        rows = []
        for field, m in self.field_metrics.items():
            for r in m["document_results"]:
                rows.append({
                    "run_id": self.run_id,
                    "schema_version": self.schema_version,
                    "git": self.git_short,
                    "document": r["document"],
                    "field": field,
                    "match": r["match"],
                    "match_type": r["match_type"],
                    "gt_value": r["gt_value"],
                    "parser_value": r["parser_value"],
                    "gt_present": int(self._has_value(r["gt_value"])),
                    "parser_present": int(self._has_value(r["parser_value"])),
                })
        df = pd.DataFrame(rows, columns=[
            "run_id","schema_version","git",
            "document","field","match","match_type",
            "gt_value","parser_value","gt_present","parser_present"
        ])
        out = Path(self.config.output_dir) / "metrics_by_document.csv"
        df.to_csv(out, index=False)
        return out

    # ---------------- Run ---------------- #

    def run_benchmark(self):
        print("Benchmarker Module v0.1")
        print("=======================")
        print(f"Ground truth dir: {self.config.ground_truth_dir}")
        print(f"Parser dir     : {self.config.parser_dir}")
        print(f"Output dir     : {self.config.output_dir}")

        if not self.config.test_documents:
            self.config.test_documents = self._discover_test_documents(limit=None)
        if not self.config.test_documents:
            print("✗ No test documents to process. Exiting early.")
            return {}

        print(f"Using test documents: {self.config.test_documents}")
        self.load_ground_truth()
        self.load_parser_results()
        self.record_environment_details()

        # Schema compliance BEFORE comparison (for required fields only)
        schema_report = self.verify_schema_compliance()

        # Metrics across ALL fields
        self.compute_all_field_metrics()
        acc = self.compute_overall_accuracy()

        # Diagnostics AFTER metrics are computed (uses document_results)
        diagnostics = self.build_diagnostics()

        # Logging & Aggregates for validation
        self._log_per_field_metrics()
        self._log_per_document_metrics()
        by_field_csv = self.export_metrics_by_field()
        by_doc_csv = self.export_metrics_by_document()

        print(f"\nOverall accuracy: {acc:.3f}")
        print(f"Aggregates saved to: {by_field_csv} and {by_doc_csv}")

        # Save outputs
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_json = out_dir / f"benchmark_{self.config.version}.json"
        out_csv = out_dir / f"benchmark_{self.config.version}.csv"

        df = pd.DataFrame([
            {"Field": f,
             "Precision": m["precision"],
             "Recall": m["recall"],
             "F1": m["f1_score"]}
            for f, m in self.field_metrics.items()
        ])
        df.to_csv(out_csv, index=False)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": self.environment_details,
                "schema_compliance": schema_report,
                "metrics": self.field_metrics,
                "diagnostics": diagnostics,
                "overall_accuracy": acc
            }, f, indent=2)

        print(f"Results saved to: {out_json} and {out_csv}")
        return self.field_metrics


# ------------------------------------------------------------------------------
# Main entry
# ------------------------------------------------------------------------------

def main():
    config = BenchmarkConfig()
    runner = BenchmarkRunner(config)
    runner.run_benchmark()


if __name__ == "__main__":
    main()
