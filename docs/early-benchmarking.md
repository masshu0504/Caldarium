# Early Benchmarking Notebook (Reproducible)

## Overview

The Early Benchmarking Notebook provides a minimal, reproducible way to test your parsing pipeline with 2-3 documents and capture key metrics for compliance and performance tracking.

## Features

- **Minimal Run**: Tests 2-3 representative documents
- **Text Recall Proxies**: Measures field extraction accuracy
- **Schema Pass Validation**: Checks if extracted data passes schema validation
- **Error Taxonomy Classification**: Categorizes errors into taxonomy buckets
- **Reproducible Results**: Records config/seed and environment hash
- **Audit Logging**: Integrates with compliance audit system

## Quick Start

### Option 1: Command Line (Recommended)
```bash
# Run from project root
docker exec -it caldarium-bench-1 python /app/bench/run_early_benchmark.py
```

### Option 2: Jupyter Notebook
```bash
# Start Jupyter in Docker container
docker exec -it caldarium-bench-1 jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root

# Open browser to http://localhost:8888
# Navigate to bench/early_benchmark_notebook.ipynb
```

### Option 3: Python Script
```python
from bench.early_benchmark_notebook import EarlyBenchmark

config = {
    "test_documents": ["invoice_T1_gen1.pdf", "invoice_T2_gen1.pdf"],
    "engines": ["pdfplumber", "pdfminer"]
}

benchmark = EarlyBenchmark(config)
results = benchmark.run_minimal_benchmark()
benchmark.print_summary()
```

## Configuration

### Default Configuration
```python
config = {
    "pdf_dir": "medical_pdfs/invoices",
    "gt_csv": "bench/data/ground_truth/invoice_fields.csv",
    "output_dir": "bench/outputs",
    "test_documents": [
        "invoice_T1_gen1.pdf",  # Simple invoice
        "invoice_T2_gen1.pdf",  # Invoice with line items
        "invoice_T3_gen1.pdf"   # Complex invoice
    ],
    "engines": ["pdfplumber", "pdfminer"],
    "seed": 42,
    "version": "v1.0"
}
```

### Customization Options
- **test_documents**: List of PDF files to test
- **engines**: Parsing engines to use ("pdfplumber", "pdfminer")
- **seed**: Random seed for reproducibility
- **version**: Version identifier for tracking

## Metrics Captured

### 1. Text Recall Proxies
Measures how well each field is extracted:
- `invoice_number`: Exact match with ground truth
- `patient_id`: Exact match with ground truth
- `invoice_date`: Exact match with ground truth
- `subtotal_amount`: Exact match with ground truth
- `total_amount`: Exact match with ground truth

### 2. Schema Pass Validation
Checks if extracted data passes schema validation:
- All required fields present
- Correct data types (numbers, strings)
- Non-empty values

### 3. Error Taxonomy Classification
Categorizes errors into taxonomy buckets:
- `SUCCESS`: All fields extracted correctly
- `MISSING_FIELD`: Required fields not found
- `SCHEMA_MISMATCH`: Data type/format issues
- `EXTRACTION_FAIL`: Parser crashed or failed
- `FIELD_PARSING_ERROR`: Regex/pattern issues

## Output Files

### JSON Results
```json
{
  "run_id": "a1b2c3d4e5f6",
  "environment_hash": "1234567890abcdef",
  "config": {...},
  "timestamp": "2025-10-10T14:15:00Z",
  "documents": [...],
  "summary": {
    "total_documents": 3,
    "total_operations": 6,
    "success_count": 4,
    "error_breakdown": {
      "SUCCESS": 4,
      "MISSING_FIELD": 2
    },
    "avg_text_recall": 0.75,
    "schema_pass_rate": 0.67
  }
}
```

### CSV Results
Detailed results in CSV format for analysis:
- Document name
- Engine used
- Error taxonomy bucket
- Schema pass status
- Text recall scores
- Processing time
- Extracted field values

## Reproducibility

### Run ID
Unique identifier for each benchmark run:
- Based on config + timestamp
- 12-character hash
- Used for result tracking

### Environment Hash
Hash of environment information:
- Python version
- Platform
- Working directory
- Configuration
- 16-character hash

### Reproducing Results
```python
# To reproduce a specific run:
config = {
    "run_id": "a1b2c3d4e5f6",
    "environment_hash": "1234567890abcdef",
    # ... other config
}

benchmark = EarlyBenchmark(config)
results = benchmark.run_minimal_benchmark()
```

## Integration with Compliance

### Audit Logging
All benchmark runs are automatically logged to the audit system:
- Document processing events
- Error classifications
- Performance metrics
- Compliance tracking

### Weekly Reports
Results feed into weekly compliance reports:
- Error breakdown by type
- Schema pass rates
- Performance trends
- Recommendations


