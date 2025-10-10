# Compliance Artifacts Documentation

## Overview
This document describes the compliance artifacts for the Caldarium x RPI Intake Agent project, including audit logging and weekly reporting capabilities.

## Audit Log Schema (v0.1)

### Purpose
Track all parsing operations for compliance, debugging, and performance monitoring.

### Schema Location
- **File**: `schemas/audit-log.schema.json`
- **Format**: JSON Schema (draft-07)

### Key Fields
- `doc_id`: Unique document identifier
- `timestamp`: ISO8601 UTC timestamp
- `stage`: Pipeline stage (parse/validate/postprocess/table_extract)
- `error_type`: Error taxonomy enum value
- `details`: Detailed operation information
- `resolution`: Error handling status
- `run_id`: Unique run identifier (seed/config hash)

### Example of Sample Log Entry
```json
{
  "doc_id": "invoice_T1_gen1.pdf",
  "timestamp": "2025-10-10T14:15:00Z",
  "stage": "parse",
  "error_type": "MISSING_FIELD",
  "details": {
    "extracted_fields": {
      "invoice_number": "INV377776",
      "patient_id": null,
      "total_amount": null
    },
    "missing_fields": ["patient_id", "total_amount"],
    "processing_time_ms": 89.5,
    "engine_used": "pdfplumber"
  },
  "resolution": "unresolved",
  "run_id": "run_a1b2c3d4"
}
```

## Weekly Report Template

### Purpose
Generate compliance reports for stakeholders with key performance metrics.

### Report Location
- **File**: `bench/weekly_report_generator.py`
- **Output**: JSON format with metrics and recommendations

### Key Metrics
1. **Totals by Error Type**: Count of each error category
2. **Schema Pass %**: Percentage of documents passing schema validation
3. **Critical Field F1**: F1 score for invoice_number, patient_id, total_amount
4. **Notes**: Human-readable analysis and recommendations

### Example Sample Report
```json
{
  "report_period": "Last 7 days",
  "generated_at": "2025-10-10T14:15:00Z",
  "metrics": {
    "total_documents": 27,
    "total_operations": 54,
    "success_rate": 66.67,
    "schema_pass_rate": 88.89,
    "critical_field_f1": 75.0,
    "error_breakdown": {
      "SUCCESS": 36,
      "MISSING_FIELD": 12,
      "TABLE_EXTRACTION_FAIL": 6
    },
    "notes": "MISSING_FIELD: 12 occurrences - improve regex patterns; TABLE_EXTRACTION_FAIL: 6 occurrences - debug table detection"
  },
  "recommendations": [
    "Develop more robust regex patterns for missing fields",
    "Investigate table extraction alternatives or improve current methods"
  ]
}
```

## Integration Instructions

### For Integration Team

#### 1. Audit Log Integration
```python
from bench.audit_logger import audit_logger, log_parsing_operation

# Log any parsing operation
log_parsing_operation(
    doc_id="document.pdf",
    stage="parse",
    error_type="SUCCESS",
    details={"extracted_fields": {...}}
)

# Get summary statistics
stats = audit_logger.get_summary_stats()
```

#### 2. Weekly Report Generation
```python
from bench.weekly_report_generator import generate_weekly_report

# Generate report for last 7 days
report = generate_weekly_report(
    audit_log_file="audit_log.jsonl",
    output_file="weekly_report.json",
    days_back=7
)
```

#### 3. Data Export
```python
# Export audit logs to CSV for analysis
audit_logger.export_logs("audit_logs.csv")

# Get logs as DataFrame
df = audit_logger.get_logs_df()
```

## File Structure
```
schemas/
├── audit-log.schema.json          # Audit log schema definition
└── error-event.schema.json        # Error event schema (existing)

bench/
├── audit_logger.py                # Audit logging implementation
├── weekly_report_generator.py     # Report generation
└── benchmark.py                   # Updated with audit logging

docs/
└── compliance-artifacts.md        # This documentation
```

## Usage Examples

### Running with Audit Logging
```bash
# Run benchmark with audit logging
docker exec -it caldarium-bench-1 python /app/bench/benchmark.py

# Generate weekly report
docker exec -it caldarium-bench-1 python /app/bench/weekly_report_generator.py
```

### Monitoring in Real-Time
```bash
# Watch audit log in real-time
docker exec -it caldarium-bench-1 tail -f /app/audit_log.jsonl

# Check current statistics
docker exec -it caldarium-bench-1 python -c "
from bench.audit_logger import audit_logger
print(audit_logger.get_summary_stats())
"
```

## Compliance Benefits

1. **Audit Trail**: Complete record of all parsing operations
2. **Error Tracking**: Systematic categorization of failures
3. **Performance Monitoring**: Processing time and success rate tracking
4. **Stakeholder Reporting**: Automated weekly reports with actionable insights
5. **Debugging Support**: Detailed logs for troubleshooting issues

## Next Steps

1. **Integration Testing**: Test audit logging with real document batches
2. **Dashboard Development**: Create web interface for monitoring
3. **Alert System**: Set up alerts for critical error thresholds
4. **Historical Analysis**: Build trend analysis capabilities
