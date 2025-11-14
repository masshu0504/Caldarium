import json
from pathlib import Path

INPUT_DIR = Path("bench/parser_outputs")
OUTPUT_FILE = Path("bench/parser_output_consent_v0.1.json")

all_records = {}

for path in INPUT_DIR.glob("*.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # infer consent ID from filename 
    # e.g. "consent_T1_gen1_nih_consent.json" → "consent_T1_gen1"
    file_stem = path.stem
    consent_id = file_stem.split("_nih_consent")[0].split("_hipaa_consent")[0]

    all_records[consent_id] = data

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_records, f, indent=2)

print(f"Merged {len(all_records)} parser outputs into {OUTPUT_FILE}")
