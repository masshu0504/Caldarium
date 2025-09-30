# Compliance Artifacts 

This document describes the compliance-related artifacts maintained for the Caldarium project by describing audit logs, schema coverage, and reproducibility notes.  

It works along with:  
- [`notice.txt`](./notice.txt) → License and attribution information.  
- [`dependency_license.csv`](./dependency_license.csv) → Dependency license inventory. 

---

## 1. Audit Logs

### Purpose
The audit logs allow us to track when and how documents are processed, capture system errors for investigation, and demonstrate adherence to schema validation and quality standards.  

### Events Captured
- **Document ingestion**:  
  - Timestamp, source location (path, URL, or MinIO bucket).  
  - File checksum (SHA256) to ensure immutability.  
- **OCR processing**:  
  - Tool used (`tesseract`, `paddleocr`) and version.  
  - Runtime duration, success/failure status.  
- **Schema validation**:  
  - Schema version applied.  
  - Fields validated vs. missing.  
  - Pass/fail outcome.  
- **Errors and warnings**:  
  - Error code (refer to [`error_taxonomy.md`](./error_taxonomy.md)).  
  - Detailed error message and context.  
- **Export events**:  
  - Data successfully exported (target system, record count).  

### Retention & Storage
- Audit logs are stored as **structured JSON** files in a dedicated `logs/` directory inside the container, and optionally written to Postgres for querying.  
- Logs are retained for **90 days** in development and **1 year** in production (policy to be reviewed).  
- Rotation is handled by Docker volume policies.  

---

## 2. Schema Coverage

### Purpose
Schema coverage ensures that medical documents parsed by Caldarium meet the defined data quality and completeness standards.  

### Method
- Schema is defined in `schema_validation.py` using **JSON Schema** and **Great Expectations** rules.  
- For each document, coverage is calculated as:  
coverage % = (# of fields successfully validated) / (total required fields)

- Coverage is logged in the audit logs and exported as a summary report (CSV/JSON).  

### Reporting
- Weekly schema coverage reports are generated automatically during CI runs.  
- Minimum target coverage: **95% of required fields present across ingested documents**.  
- Reports are stored under `compliance/reports/schema_coverage/`.  

---

## 3. Reproducibility Notes

### Containerization
- All services (FastAPI API, Postgres, MinIO, Label Studio, helper container) are defined in `docker-compose.yml`.  
- Developers can reproduce the environment by running:  
```bash
docker compose up -d --build