#!/usr/bin/env python

import json
from pathlib import Path

GX_VALIDATIONS_DIR = Path("gx") / "uncommitted" / "validations"
STANDARDIZATION_REPORT_PATH = Path("output") / "standardization_validation_report.jsonl"
SUMMARY_METRICS_PATH = Path("output") / "main_summary_metrics_week8.json"


def collect_expectation_results():
    all_results = []

    if not GX_VALIDATIONS_DIR.exists():
        print(f"No validations found under {GX_VALIDATIONS_DIR}")
        return all_results

    for path in GX_VALIDATIONS_DIR.rglob("*.json"):
        with path.open() as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        meta = data.get("meta", {}) or {}
        suite_name = meta.get("expectation_suite_name")
        run_id = meta.get("run_id")

        batch_kwargs = meta.get("batch_kwargs") or meta.get("batch_spec") or {}
        asset_name = (
            batch_kwargs.get("data_asset_name")
            or batch_kwargs.get("asset_name")
            or batch_kwargs.get("path")
        )

        for res in data.get("results", []):
            expectation_config = res.get("expectation_config", {})
            result = res.get("result", {})

            all_results.append(
                {
                    "suite_name": suite_name,
                    "asset_name": asset_name,
                    "run_id": run_id,
                    "expectation_type": expectation_config.get("expectation_type"),
                    "kwargs": expectation_config.get("kwargs"),
                    "success": res.get("success"),
                    "element_count": result.get("element_count"),
                    "unexpected_count": result.get("unexpected_count"),
                    "unexpected_percent": result.get("unexpected_percent"),
                    "partial_unexpected_list": result.get("partial_unexpected_list"),
                }
            )

    return all_results


def write_jsonl(expectation_results):
    STANDARDIZATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STANDARDIZATION_REPORT_PATH.open("w") as f:
        for r in expectation_results:
            f.write(json.dumps(r) + "\n")


def compute_standardization_pass_rate(expectation_results):
    total_elements = 0
    total_unexpected = 0

    for r in expectation_results:
        ec = r.get("element_count")
        uc = r.get("unexpected_count")

        if ec is not None and uc is not None:
            total_elements += ec
            total_unexpected += uc

    if total_elements == 0:
        return None

    return (total_elements - total_unexpected) / total_elements


def update_summary_metrics(pass_rate):
    metrics = {}

    if SUMMARY_METRICS_PATH.exists():
        try:
            with SUMMARY_METRICS_PATH.open() as f:
                metrics = json.load(f)
        except json.JSONDecodeError:
            metrics = {}

    metrics["standardization_pass_rate"] = pass_rate

    with SUMMARY_METRICS_PATH.open("w") as f:
        json.dump(metrics, f, indent=2)


def main():
    results = collect_expectation_results()

    if not results:
        print("No GE validation results found.")
        return

    write_jsonl(results)
    pass_rate = compute_standardization_pass_rate(results)
    update_summary_metrics(pass_rate)

    print("standardization_validation_report.jsonl written.")
    print("standardization_pass_rate =", pass_rate)


if __name__ == "__main__":
    main()