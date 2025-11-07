#!/usr/bin/env python3
"""
Benchmark Module v0.1 (final fixed)
===================================

A comprehensive benchmarking tool for comparing parser JSON outputs against
ground truth labels. Computes precision, recall, F1-score, and overall accuracy
per field and document.

Improvements:
- Correct path resolution for your current repo structure
- Robust value presence check (_has_value)
- Fixed ambiguous truth value error for array/list fields
"""

import pandas as pd
import json
import numpy as np
import sys
import hashlib
import platform
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import warnings
import random

warnings.filterwarnings("ignore")

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------

class BenchmarkConfig:
    """Configuration class for benchmark parameters"""

    def __init__(self):
        self.version = "v0.1"

        # Adjusted for your structure: Caldarium/PDFLogicCode and Caldarium/parser_json_output
        self.ground_truth_dir = HERE.parent / "PDFLogicCode" / "output_invoices"
        self.parser_dir = HERE.parent / "parser_json_output"
        self.output_dir = HERE / "outputs"

        # Leave test_documents None → auto-detect overlap
        self.test_documents: Optional[List[str]] = None
        self.parser_suffix = "_regex.json"

        self.fields_to_evaluate = [
            "invoice_number", "due_date", "patient_name", "subtotal_amount",
            "invoice_date", "total_amount", "line_items"
        ]


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
                gt_num = float(str(gt_norm).replace('$', '').replace(',', ''))
                parser_num = float(str(parser_norm).replace('$', '').replace(',', ''))
                if abs(gt_num - parser_num) < 0.01:
                    return True, "numeric_match"
            except Exception:
                pass

        date_fields = ['invoice_date', 'due_date', 'admission_date', 'discharge_date']
        if field_name in date_fields:
            try:
                gt_date = str(gt_norm).replace('-', '').replace('/', '')
                parser_date = str(parser_norm).replace('-', '').replace('/', '')
                if gt_date == parser_date:
                    return True, "date_match"
            except Exception:
                pass

        return False, "mismatch"

    @staticmethod
    def compare_line_items(gt_items, parser_items):
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

        if len(gt_norm) == len(pr_norm):
            matches = 0
            for g in gt_norm:
                for p in pr_norm:
                    if (g["description"] == p["description"] and
                        abs(g["amount"] - p["amount"]) < 0.01 and
                        g["code"] == p["code"]):
                        matches += 1
                        break
            if matches == len(gt_norm):
                return True, "exact_match"
            return False, f"partial_match_{matches}/{len(gt_norm)}"

        return False, f"length_mismatch_{len(gt_norm)}_vs_{len(pr_norm)}"


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

    def _has_value(self, v) -> bool:
        """Robust check for value presence (handles scalars, lists, dicts, arrays)"""
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

    def _discover_test_documents(self, limit: Optional[int] = 3) -> List[str]:
        """
        Find doc names present in BOTH parser and ground-truth folders.
        Parser files: <doc_name> + _regex.json
        GT files    : invoice_<doc_name>.json
        """
        parser_docs = set()
        for p in self.config.parser_dir.glob(f"*{self.config.parser_suffix}"):
            # p.name includes extension; strip exactly the suffix '_regex.json'
            # e.g. 'invoice_T1_gen1_regex.json' -> 'invoice_T1_gen1'
            name = p.name[:-len(self.config.parser_suffix)]
            if name:
                parser_docs.add(name)

        gt_docs = set()
        for p in self.config.ground_truth_dir.glob("invoice_*.json"):
            # 'invoice_invoice_T1_gen1.json' -> doc = 'invoice_T1_gen1'
            stem = p.stem
            if stem.startswith("invoice_"):
                doc = stem[len("invoice_"):]
                if doc:
                    gt_docs.add(doc)

        overlap = sorted(parser_docs & gt_docs)
        if limit:
            overlap = overlap[:limit]

        if not overlap:
            print("✗ No overlapping documents found between parser outputs and ground truth.")
        else:
            print(f"✓ Overlapping documents: {overlap}")
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
            fname = f"{doc}{self.config.parser_suffix}"
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

            gt_has_value = self._has_value(gt_value)
            pr_has_value = self._has_value(pr_value)

            if gt_has_value:
                results["gt_present"] += 1
            if pr_has_value:
                results["parser_present"] += 1
            if gt_has_value and pr_has_value:
                results["both_present"] += 1

            if field_name == "line_items":
                is_match, mtype = FieldComparator.compare_line_items(gt_value, pr_value)
            else:
                is_match, mtype = FieldComparator.compare_scalar_field(gt_value, pr_value, field_name)
            if is_match:
                results["matches"] += 1

            results["document_results"].append({
                "document": doc,
                "gt_value": gt_value,
                "parser_value": pr_value,
                "match": is_match,
                "match_type": mtype
            })

        prec = results["matches"] / results["parser_present"] if results["parser_present"] else 0.0
        rec = results["matches"] / results["gt_present"] if results["gt_present"] else 0.0
        f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) else 0.0

        results.update({"precision": prec, "recall": rec, "f1_score": f1})
        return results

    def compute_all_field_metrics(self):
        print("Computing metrics for all fields...")
        metrics = {}
        for f in self.config.fields_to_evaluate:
            print(f"Computing metrics for field: {f}")
            metrics[f] = self.compute_field_metrics(f)
        self.field_metrics = metrics
        return metrics

    def compute_overall_accuracy(self):
        total = sum(m["total_documents"] for m in self.field_metrics.values())
        matches = sum(m["matches"] for m in self.field_metrics.values())
        return matches / total if total else 0.0

    # ---------------- Run ---------------- #

    def run_benchmark(self):
        print("Benchmark Module v0.1")
        print("=====================")
        print(f"Ground truth dir: {self.config.ground_truth_dir}")
        print(f"Parser dir     : {self.config.parser_dir}")
        print(f"Output dir     : {self.config.output_dir}")

        if not self.config.test_documents:
            self.config.test_documents = self._discover_test_documents(limit=3)
        if not self.config.test_documents:
            print("✗ No test documents to process. Exiting early.")
            return {}

        print(f"Using test documents: {self.config.test_documents}")
        self.load_ground_truth()
        self.load_parser_results()
        self.compute_all_field_metrics()

        acc = self.compute_overall_accuracy()
        print(f"\nOverall accuracy: {acc:.3f}")

        # Save outputs
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_json = out_dir / f"benchmark_{self.config.version}.json"
        out_csv = out_dir / f"benchmark_{self.config.version}.csv"

        df = pd.DataFrame([
            {"Field": f, "Precision": m["precision"], "Recall": m["recall"], "F1": m["f1_score"]}
            for f, m in self.field_metrics.items()
        ])
        df.to_csv(out_csv, index=False)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({"metrics": self.field_metrics, "overall_accuracy": acc}, f, indent=2)

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
