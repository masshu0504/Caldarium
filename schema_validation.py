import argparse
import json
from jsonschema import validate, ValidationError

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

