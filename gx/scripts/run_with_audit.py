#!/usr/bin/env python3
import argparse, json, os, sys
from datetime import datetime, timezone
from collections import defaultdict

ROLE = "validator"
SCHEMA_VERSION = "invoice_v1_reset"

def now_iso(): return datetime.now(timezone.utc).isoformat()
def get_actor(): return os.environ.get("ACTOR", os.environ.get("USER", "unknown_actor"))
def get_run_id(): return os.environ.get("RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def base_line(doc_id, run_id, actor):
    return {
        "timestamp": now_iso(),
        "doc_id": doc_id,
        "role": ROLE,
        "actor": actor,
        "action": None,
        "run_id": run_id,
        "field": None,
        "from": None,
        "to": None,
        "status": None,
        "schema_version": SCHEMA_VERSION,
        "meta": {},
    }

def run_checkpoint_and_audit(args):
    import great_expectations as ge
    try:
        from great_expectations.data_context import DataContext  # GE < 1.0
    except Exception:
        from great_expectations.data_context import FileDataContext as DataContext  # GE 1.x

    actor   = get_actor()
    run_id  = get_run_id()
    doc_id  = args.asset
    logpath = args.log

    append_jsonl(logpath, {
        **base_line(doc_id, run_id, actor),
        "action": "validate_start",
        "status": "success",
        "meta": {
            "validator_version": ge.__version__,
            "checkpoint": args.checkpoint,
            "input_path": args.input,
        },
    })

    context = DataContext(context_root_dir=os.environ.get("GE_PROJECT_DIR"))
    res = context.run_checkpoint(checkpoint_name=args.checkpoint)

    # -------- normalize GE result shapes --------
    def extract_success(r):
        if isinstance(r, dict):
            return bool(r.get("success"))
        return bool(getattr(r, "success", False))

    def extract_results_list(r):
        """
        Return a flat list of expectation-level results.
        Works for:
          - dict: {"run_results": { id: {"validation_result": {"results": [...]}}}, "success": ...}
          - objecty: r.run_results -> same dict as above
          - older dict shape: {"validation_result": {"results": [...]}}
        """
        # object -> dict
        if not isinstance(r, dict) and hasattr(r, "run_results"):
            rr = getattr(r, "run_results")
            if isinstance(rr, dict):
                out = []
                for v in rr.values():
                    vr = v.get("validation_result") if isinstance(v, dict) else None
                    if vr and isinstance(vr, dict) and "results" in vr:
                        out.extend(vr["results"])
                if out:
                    return out
        # dict with run_results
        if isinstance(r, dict) and "run_results" in r and isinstance(r["run_results"], dict):
            out = []
            for v in r["run_results"].values():
                vr = v.get("validation_result", {})
                out.extend(vr.get("results", []))
            return out
        # dict with validation_result directly
        if isinstance(r, dict) and "validation_result" in r:
            return r["validation_result"].get("results", [])
        # fallback empty
        return []

    overall_success = extract_success(res)
    results_list = extract_results_list(res)

    failed_by_field = defaultdict(list)
    for r in results_list:
        # each r should be a dict with "success", "expectation_config", etc.
        success = r.get("success", False)
        if success:
            continue
        exp_cfg = r.get("expectation_config", {}) or {}
        exp_type = exp_cfg.get("expectation_type")
        kwargs = exp_cfg.get("kwargs", {}) or {}
        column = kwargs.get("column")  # None for table-level
        meta_bits = {
            "expectation_type": exp_type,
            "kwargs": kwargs,
            "result": r.get("result", {}),
        }
        key = column or "<table>"
        failed_by_field[key].append(meta_bits)

    if overall_success:
        append_jsonl(logpath, {
            **base_line(doc_id, run_id, actor),
            "action": "doc_validate_pass",
            "status": "pass",
            "meta": {
                "validator_version": ge.__version__,
                "checkpoint": args.checkpoint,
                "summary": {
                    "total_expectations": len(results_list),
                    "failed_fields": 0
                }
            }
        })
        return 0
    else:
        for field_name, failures in failed_by_field.items():
            append_jsonl(logpath, {
                **base_line(doc_id, run_id, actor),
                "action": "field_validate_fail",
                "status": "fail",
                "field": None if field_name == "<table>" else field_name,
                "meta": {
                    "validator_version": ge.__version__,
                    "checkpoint": args.checkpoint,
                    "failures": failures,
                    "failed_expectation_count": len(failures),
                },
            })
        # If there were no expectation-level records but success==False, emit one generic fail
        if not failed_by_field:
            append_jsonl(logpath, {
                **base_line(doc_id, run_id, actor),
                "action": "field_validate_fail",
                "status": "fail",
                "field": None,
                "meta": {
                    "validator_version": ge.__version__,
                    "checkpoint": args.checkpoint,
                    "note": "Validation reported failure but no expectation results were found.",
                },
            })
        return 1

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--asset", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--log", default="/output/audit_log.jsonl")
    args = p.parse_args()
    sys.exit(run_checkpoint_and_audit(args))

if __name__ == "__main__":
    main()