import json, os, re, sys
from datetime import datetime

INDEX_PATH = "bench/ground_truth_index_consent_v0.1.json"
SCHEMA_PATH = "bench/consent_schema_v0.1.json"
ALIGNED_OUT = "bench/ground_truth_aligned_consent_v0.1.json"
ERRORS_OUT = "bench/ground_truth_alignment_errors_v0.1.jsonl"

WS_RX = re.compile(r"\s+")
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y")

def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def to_iso_date(s):
    if s is None:
        return None
    s = str(s).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            continue
    # already looks like YYYY-MM-DD?
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    # give up: not a valid date
    return s  # return as-is; validator will flag

def trim_str(v):
    if v is None:
        return None
    v = str(v)
    v = WS_RX.sub(" ", v.strip())
    return v

def normalize(record):
    """Trim strings and coerce date-like keys to ISO."""
    out = {}
    for k, v in record.items():
        if isinstance(v, str):
            v = trim_str(v)
        elif isinstance(v, list):
            v = [trim_str(x) if isinstance(x, str) else x for x in v]
        elif isinstance(v, dict):
            # do not recurse into nested objects; schema has flat structure
            pass
        out[k] = v

    # date coercions (schema has exactly these)
    for dk in ("patient_dob", "date", "expiration_date"):
        if dk in out and out[dk] is not None:
            out[dk] = to_iso_date(out[dk])

    return out

def strict_align(data, schema, doc_id, path):
    props = schema["properties"]
    required = set(schema.get("required", []))
    allow_keys = set(props.keys())

    data = normalize(data)

    # remove unknown keys
    unknown = [k for k in list(data.keys()) if k not in allow_keys]
    for k in unknown:
        data.pop(k, None)

    # fill missing optional fields explicitly with null
    for k in allow_keys:
        if k not in data:
            data[k] = None

    # coerce types where possible: everything in this schema is string or null
    for k, spec in props.items():
        t = spec["type"]
        allowed = t if isinstance(t, list) else [t]
        v = data.get(k)

        if v is None:
            continue

        # booleans/numbers -> string
        if "string" in allowed and not isinstance(v, str):
            data[k] = str(v)

        # date format check will be done in validate()
    return data, unknown

def validate(data, schema):
    """Return list of error messages for this object."""
    props = schema["properties"]
    required = set(schema.get("required", []))
    errs = []

    # required
    for k in required:
        if data.get(k) in (None, ""):
            errs.append(f"required_missing:{k}")

    # type + format checks
    for k, spec in props.items():
        v = data.get(k)
        allowed = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]

        if v is None:
            if "null" not in allowed and k in required:
                errs.append(f"type_violation:{k}=null_not_allowed")
            continue

        if "string" not in allowed:
            errs.append(f"type_violation:{k}=expected_{allowed}_got_string")
            continue

        # format: date (YYYY-MM-DD)
        if spec.get("format") == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v or ""):
                errs.append(f"format_violation:{k}=not_YYYY-MM-DD")

    return errs

def main():
    if not os.path.exists(INDEX_PATH):
        print(f"ERROR: missing {INDEX_PATH}")
        sys.exit(1)
    if not os.path.exists(SCHEMA_PATH):
        print(f"ERROR: missing {SCHEMA_PATH}")
        sys.exit(1)

    index = load_json(INDEX_PATH)
    schema = load_json(SCHEMA_PATH)

    aligned_docs = []
    os.makedirs(os.path.dirname(ERRORS_OUT), exist_ok=True)
    err_f = open(ERRORS_OUT, "w", encoding="utf-8")

    count = 0
    for rec in index["docs"]:
        fp = rec["file"]
        doc_id = rec.get("document_id") or os.path.splitext(os.path.basename(fp))[0]
        if not os.path.exists(fp):
            err = {"document_id": doc_id, "file": fp, "errors": ["file_not_found"]}
            err_f.write(json.dumps(err) + "\n")
            continue

        try:
            raw = load_json(fp)
        except Exception as e:
            err = {"document_id": doc_id, "file": fp, "errors": [f"json_load_error:{e}"]}
            err_f.write(json.dumps(err) + "\n")
            continue

        # Align strictly to schema
        aligned, unknown = strict_align(raw, schema, doc_id, fp)
        errors = validate(aligned, schema)
        if unknown:
            errors.append(f"unknown_keys_removed:{','.join(unknown)}")

        # log errors (if any)
        if errors:
            err_f.write(json.dumps({"document_id": doc_id, "file": fp, "errors": errors}) + "\n")

        aligned_docs.append({
            "document_id": doc_id,
            "template_id": rec.get("template_id"),
            "schema_version": rec.get("schema_version"),
            "file": fp,
            "data": aligned
        })
        count += 1

    err_f.close()

    os.makedirs(os.path.dirname(ALIGNED_OUT), exist_ok=True)
    with open(ALIGNED_OUT, "w", encoding="utf-8") as out:
        json.dump({"docs": aligned_docs}, out, indent=2, ensure_ascii=False)

    print(f"Wrote {ALIGNED_OUT} with {count} records.")
    print(f"Validation report: {ERRORS_OUT}")

if __name__ == "__main__":
    main()
