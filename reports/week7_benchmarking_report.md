# Week 7 Benchmarking Report v2.0

## 0. Hybrid k Consent QA Summary

- Hybrid QA Score (k): **0.9440** → **94.37%**

- Micro Precision / Recall / F1: **0.9843** / **0.9488** / **0.9662**

- Critical fields avg F1: **0.7500**

- Target thresholds: k ≥ **0.85**, critical F1 ≥ **0.95**

- Status (Hybrid k): Met

- Status (Critical fields F1): Below target


---

## 1. Consent Benchmark Summary

### 1.1 Overall Metrics

- Total fields: **528**

- Matches: **500**

- Accuracy / F1: **0.9470**


### 1.2 Critical Fields (Hybrid k Proxy via F1)

- Fields: `patient_name, consent_type, provider_signature`

- Total: **16**

- Matches: **12**

- F1 (approx.): **0.7500**


## 2. Blank Field & Mapping Validation Analysis

- Blank field entries reviewed: **0**

- Auto-filled blank fields: **0**


### 2.1 Schema Validation

- Total fields validated: **544**

- Valid fields: **528**

- Invalid fields: **16**

- Validation rate: **0.9706**


## 3. Duplicate Record Trial Summary

- Duplicate pairs evaluated: **5**

- `merge`: **5**


## 4. Determinism Verification Results

- Deterministic: **True**

- Hash run1: `1b5f3c28dc877cdb06338d0fbaa2dd7c86d9ed43eb946905eaf246386c89e71e`

- Hash run2: `1b5f3c28dc877cdb06338d0fbaa2dd7c86d9ed43eb946905eaf246386c89e71e`


## 5. Recommendations

### 5.1 For Minna (Parser)

- Review fields with repeated mapping or format errors.

- Prioritize critical fields where F1 < target threshold.

- Investigate over/under-filling of blank fields.


### 5.2 For Jay (Validation)

- Confirm schema assumptions for fields with high invalid rate.

- Align blank field rules with parser auto-fill logic.

- Define explicit handling for borderline duplicate cases.
