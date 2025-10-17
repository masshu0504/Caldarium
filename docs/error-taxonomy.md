# Error Taxonomy (v2)

**Purpose:**  
Standardize how the Intake Agent reports failures across parsing, validation, and post-processing for digital-native documents.

## Core Categories
- `EXTRACTION_FAIL` — Failed to read or extract structured text/data from a digital document (e.g., corrupted PDF, parser crash).  
- `SCHEMA_MISMATCH` — Extracted data does not conform to the expected schema (invalid types, missing required fields, or unexpected values).  
- `MISSING_FIELD` — A required field was not found in the parsed payload.  
- `TEXT_NOISE` — The extracted text contains unreadable or invalid characters that prevent successful parsing or validation.
- `TABLE_EXTRACTION_FAIL` — Table extraction tools (Camelot, Tabula) failed to detect or extract tabular data.
- `FIELD_PARSING_ERROR` — Specific field extraction failed due to regex pattern issues or text quality problems.

## Live Example from Benchmark Runs (2025-10-10)

### MISSING_FIELD
- **Document**: `invoice_T1_gen1.pdf`
- **Issue**: `pred_patient_id: empty, pred_total_amount: empty` (pdfplumber extracted 430.0 subtotal)
- **Fix**: Add patient ID regex patterns; improve total amount detection when subtotal exists

### FIELD_PARSING_ERROR
- **Document**: `invoice_T3_gen1.pdf`
- **Issue**: pdfminer extracted 'Date' instead of 'INV244194' for invoice_number
- **Fix**: pdfminer text extraction quality issues; use pdfplumber for better results

### TABLE_EXTRACTION_FAIL
- **Document**: All invoices (27 attempts)
- **Issue**: `cell_match_rate: empty` for all camelot_lattice, camelot_stream, and tabula extractions
- **Fix**: Complete table extraction failure; investigate PDF table structure or use alternative methods

### SCHEMA_MISMATCH
- **Document**: `invoice_T2_gen1.pdf`
- **Issue**: `em_invoice_date: 0` (extracted 1998-05-28 vs expected 1998-04-28)
- **Fix**: Date format mismatch; normalize date parsing to handle different formats

## Stages
- `PARSER`, `VALIDATOR`, `POSTPROC`

## Error Event Shape (see `schemas/error-event.schema.json`)
- `error_code` (required): one of the categories above.  
- `stage` (required): one of the stages above.  
- `message` (required): human-readable summary.  
- `timestamp` (required): ISO8601 UTC timestamp.  
- `source` (optional): `{ file_path?, document_id? }` — identifies the file or record that produced the error.  
- `details` (optional): any extra debug info (e.g., missing field names, validation results, confidence scores).

## Versioning
- **v2:** Removed all OCR and EXTRACTOR references; taxonomy now applies strictly to digital-native parsing and validation stages.  
- **v1:** Original release including OCR terminology.

