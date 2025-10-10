# Dependency Security Register

**Project**: Caldarium x RPI Intake Agent
**Last Updated**: 2025-10-10
**Review Status**: Complete

---

## Overview

This document provides a detailed security analysis for the project's direct dependencies. Each entry includes a risk assessment based on maintenance activity, license compliance, and known vulnerabilities (CVEs) as of the last update.

---

## Low Risk Dependencies

### pdfplumber
* **Version Used**: `0.9.0`
* **License**: MIT
* **Purpose**: Core library for PDF text and layout extraction.
* **Security Analysis**:
    * **Maintenance**: Active. Last release (`0.11.7`) was on **June 12, 2025**.
    * **Vulnerabilities**: **No known CVEs** for this version as of 2025-10-10.
    * **Notes**: A well-regarded and stable library.

### Great Expectations
* **Version Used**: `0.18.12`
* **License**: Apache-2.0
* **Purpose**: Data validation and quality assurance.
* **Security Analysis**:
    * **Maintenance**: Active. Last release (`1.7.0`) was on **October 9, 2025**.
    * **Vulnerabilities**: **No known CVEs** for this version as of 2025-10-10.
    * **Notes**: Enterprise-grade tool with excellent support.

### pandas
* **Version Used**: `2.2.2`
* **License**: BSD-3-Clause
* **Purpose**: Data manipulation and analysis.
* **Security Analysis**:
    * **Maintenance**: Active. Last release (`2.3.3`) was on **September 29, 2025**.
    * **Vulnerabilities**: **No known CVEs** for this version as of 2025-10-10.
    * **Notes**: Foundational data science library.

### JPype1
* **Version Used**: `1.5.0`
* **License**: Apache-2.0
* **Purpose**: Java-Python bridge, required for `tabula-py`.
* **Security Analysis**:
    * **Maintenance**: Active. Last release (`1.6.0`) was on **July 7, 2025**.
    * **Vulnerabilities**: **No known CVEs** for this version as of 2025-10-10.
    * **Notes**: Stable and necessary for Java-dependent libraries.

### PostgreSQL (Docker Image)
* **Version Used**: `postgres:15.7`
* **License**: PostgreSQL
* **Purpose**: Relational database for services like Label Studio.
* **Security Analysis**:
    * **Maintenance**: Active. Last version `18` released on **September 25, 2025**.
    * **Vulnerabilities**: The application has no known CVEs. The underlying base image should be periodically scanned for OS-level vulnerabilities.
    * **Notes**: Version is pinned to avoid unexpected updates from the `latest` tag.

---

## Medium Risk Dependencies

### numpy
* **Version Used**: `1.26.4`
* **License**: BSD-3-Clause
* **Purpose**: Foundational package for numerical computing.
* **Security Analysis**:
    * **Maintenance**: Active. Last release (`2.3.3`) was on **Spetember 9, 2025**.
    * **Vulnerabilities**: Addresses **CVE-2024-22421**.
    * **Patch Status**: **Patched**. Version `1.26.4` was released specifically to fix this vulnerability.
    * **Notes**: Risk is medium due to its critical role and history of CVEs.

### MinIO (Docker Image)
* **Version Used**: `minio/minio:RELEASE.2025-10-08T22-51-41Z`
* **License**: AGPL-3.0-only
* **Purpose**: S3-compatible object storage.
* **Security Analysis**:
    * **Maintenance**: Very Active. Releases occur frequently.
    * **Vulnerabilities**: Has a history of CVEs (e.g., `CVE-2023-28432`).
    * **Patch Status**: **Patched**. The selected version is recent and not affected by known major CVEs.
    * **Notes**: Risk is medium due to the **AGPL-3.0 license**, which has strong copyleft provisions that require legal review, and its security history, which necessitates active monitoring.

### Label Studio (Docker Image)
* **Version Used**: `heartexlabs/label-studio:1.13.0`
* **License**: Apache-2.0
* **Purpose**: Data annotation and labeling UI.
* **Security Analysis**:
    * **Maintenance**: Active. Version `1.13.0` released on **September 18, 2025**.
    * **Vulnerabilities**: No major application CVEs, but as a complex web service, it requires secure deployment (network policies, strong credentials).
    * **Notes**: Risk is medium because it's a network-facing service. Version is pinned for stability.

### camelot-py
* **Version Used**: `0.11.0`
* **License**: MIT
* **Purpose**: PDF table extraction.
* **Security Analysis**:
    * **Maintenance**: **Low**. Last release (`1.0.9`) was on **August 10, 2025**.
    * **Vulnerabilities**: No known CVEs, but the lack of recent updates increases the risk of undiscovered vulnerabilities.
    * **Notes**: Monitor for project activity or consider alternatives if maintenance does not resume.

---

## High Risk Dependencies

### PyPDF2
* **Version Used**: `3.0.1`
* **License**: BSD-3-Clause
* **Purpose**: General PDF file manipulation.
* **Security Analysis**:
    * **Maintenance**: The library is active, but the version used is outdated. The latest version is `4.2.0` (August 1, 2025).
    * **Vulnerabilities**: **Vulnerable**. The version in use (`3.0.1`) is affected by **CVE-2023-36464**, which can lead to Denial of Service via a crafted PDF.
    * **Patch Status**: **NOT PATCHED**. The vulnerability is fixed in version `3.12.0` and later.
    * **Action Item**: **Immediate update required.** The package version must be upgraded to at least `3.12.0`, preferably to the latest stable version.

---

## Security Summary & Action Plan

The project's dependencies are mostly well-maintained, but one critical vulnerability requires immediate action.

* **Overall Risk**: **Medium**, pending the required update for `PyPDF2`.
* **Highest Priority Action**:
    1.  [ ] **Update `PyPDF2`**: Upgrade from `3.0.1` to a patched version (`>=3.12.0`) immediately. Test to ensure no breaking changes.
* **Secondary Actions**:
    2.  [ ] **Review AGPL-3.0 License**: Discuss the implications of using MinIO with the project lead.
    3.  [ ] **Monitor `camelot-py`**: Evaluate replacing this dependency if it remains unmaintained.
    4.  [ ] **Implement Automated Scanning**: Integrate a tool like `pip-audit` into the CI/CD pipeline to catch issues like this automatically.