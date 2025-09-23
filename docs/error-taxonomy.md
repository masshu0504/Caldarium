# Error Taxonomy (v1)

**Purpose:** Standardize how the Intake Agent reports failures across OCR, extraction, parsing, and validation.

## Core Categories
- `EXTRACTION_FAIL` — Could not extract text/data from source (e.g., unreadable PDF, parser crashed).
- `SCHEMA_MISMATCH` — Extracted data doesn’t conform to the target schema (types, enums, additional/incorrect fields).
- `MISSING_FIELD` — A required field is absent in the extracted payload.
- `OCR_NOISE` — OCR output is too noisy/garbled to parse or validate.

## Stages
- `OCR`, `PARSER`, `VALIDATOR`, `POSTPROC`

## Error Event Shape (see schemas/error-event.schema.json)
- `error_code` (required): one of the categories above
- `stage` (required): one of the stages above
- `message` (required): human-friendly summary
- `timestamp` (required): ISO8601 UTC
- `source` (optional): `{ file_path?, document_id? }`
- `details` (optional): any extra debug info (e.g., missing field names, confidence scores)

## Examples
See `tests/test_error_taxonomy.py`.

## Versioning
Bump this file’s header (v2, v3…) for breaking changes.
