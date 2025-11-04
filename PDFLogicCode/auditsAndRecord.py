
import os
import json
from datetime import datetime
from openai import OpenAI

OUTPUT_DIR="output_invoices"
OUTPUT_AUDIT_FILE="output_audit.txt"
MODEL_NAME="openai/gpt-5"
TEMPERATURE=0.4
FILES_PAUSED = "filesPaursed.json"

def record_parsed_file(paused_path: str, filename: str) -> None:
    """Record `filename` into a JSON array at `paused_path` (create if missing).
    Non-fatal: prints a warning on failure.
    """
    try:
        if os.path.exists(paused_path):
            with open(paused_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        if filename not in data:
            data.append(filename)
            with open(paused_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: failed to record parsed file {filename}: {e}")


def log_audit(filename, fields_filled, fields_null, system_prompt, outputJsonString):
    """Append an audit record to the audit log."""
    with open(OUTPUT_AUDIT_FILE, "a", encoding="utf-8") as audit:
        audit.write("\n" + "=" * 60 + "\n")
        audit.write(f"File: {filename}\n")
        audit.write(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}\n")
        audit.write(f"Model: {MODEL_NAME}\n")
        audit.write(f"Temperature: {TEMPERATURE}\n")
        audit.write(f"System Prompt:\n{system_prompt}\n")
        audit.write(f"Fields auto-filled ({len(fields_filled)}): {', '.join(fields_filled)}\n")
        audit.write(f"Fields left blank ({len(fields_null)}): {', '.join(fields_null)}\n")
        audit.write(f"Raw output:\n{outputJsonString}\n")
        audit.write("=" * 60 + "\n\n")

        cleaned = (
            outputJsonString.strip()
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON for {filename}: {e}")
            print("Raw output:\n", outputJsonString[:1000], "...\n")
            return

        if isinstance(parsed, list) and len(parsed) == 1:
            invoice_data = parsed[0]
        else:
            invoice_data = parsed

        if not isinstance(invoice_data, dict):
            print(f"Unexpected parsed structure for {filename}: expected object, got {type(invoice_data)}")
            return

        fields_filled = [k for k, v in invoice_data.items() if v not in (None, "", [], {})]
        fields_null = [k for k, v in invoice_data.items() if v in (None, "", [], {})]
        

        output_filename = os.path.join(OUTPUT_DIR, f"{os.path.splitext(filename)[0]}.json")
        try:
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(invoice_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to write {output_filename}: {e}")
            return





