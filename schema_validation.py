import argparse
import json
from jsonschema import validate, ValidationError
from pathlib import Path
from errors import ErrorEvent, ErrorCode, Stage

def validate_invoice(payload: dict, source_path: str | None = None) -> bool:
        schema_path = Path("schemas/invoice.json")
        schema = json.loads(schema_path.read_text())
        try:
            validate(instance=payload, schema=schema)
            return True
        except ValidationError as e:
            # Decide: missing field vs schema mismatch
            # Heuristic: if 'is a required property' appears, call it MISSING_FIELD
            message = str(e.message)
            if "is a required property" in message:
                code = ErrorCode.MISSING_FIELD
                details = {"missing_property": getattr(e, "path", None) and list(e.path),
                        "validator": e.validator, "validator_value": e.validator_value}
            else:
                code = ErrorCode.SCHEMA_MISMATCH
                details = {"error": message,
                        "path": list(e.path),
                        "validator": e.validator,
                        "validator_value": e.validator_value}

            event = ErrorEvent(
                error_code=code,
                stage=Stage.VALIDATOR,
                message=f"Invoice schema validation failed: {message}",
                source={"file_path": source_path} if source_path else None,
                details=details
            )
            print("INTAKE_ERROR " + json.dumps(event.to_dict()))  # simple JSON-line log
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Validate a JSON instance against the invoice schema"
    )
    parser.add_argument(
        "instance",
        help="Path to the JSON instance file (e.g., invoice_T1_gen1.json)"
    )
    parser.add_argument(
        "-s", "--schema",
        default="schemas/invoice.json",
        help="Path to the JSON schema file (default: invoice.json)"
    )

    args = parser.parse_args()

    # Load the schema
    with open(args.schema, "r", encoding="utf-8") as f:
        invoice_schema = json.load(f)

    # Load the instance
    with open(args.instance, "r", encoding="utf-8") as f:
        invoice_data = json.load(f)

    # Validate with detailed error handling
    try:
        validate(instance=invoice_data, schema=invoice_schema)
        print(f"✅ Validation passed for '{args.instance}'")
    except ValidationError as e:
        print(f"❌ Validation failed for '{args.instance}'")
        print("Error message:")
        print(f"  {e.message}")
        if e.path:
            print("Failed at field path:")
            print(f"  {' -> '.join(map(str, e.path))}")
        if e.schema_path:
            print("Schema path:")
            print(f"  {' -> '.join(map(str, e.schema_path))}")
    

if __name__ == "__main__":
    main()

