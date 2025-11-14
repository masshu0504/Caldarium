import os, re, json, pdfplumber

# -----------------------------
# FOLDER SETUP
# -----------------------------
pdf_folder = "medical_pdfs/intakes"
parsed_text_folder = "parsed_texts_intakes"
json_output_folder = "json_intakes"

os.makedirs(pdf_folder, exist_ok=True)
os.makedirs(parsed_text_folder, exist_ok=True)
os.makedirs(json_output_folder, exist_ok=True)

# -----------------------------
# STEP 1: PDF → TEXT
# -----------------------------
for filename in os.listdir(pdf_folder):
    if filename.lower().endswith(".pdf"):
        pdf_path = os.path.join(pdf_folder, filename)
        text_path = os.path.join(parsed_text_folder, f"{os.path.splitext(filename)[0]}.txt")

        print(f"Parsing {filename}...")
        with pdfplumber.open(pdf_path) as pdf:
            all_text = ""
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                all_text += f"\n--- Page {i+1} ---\n{text}\n"

        with open(text_path, "w", encoding="utf-8") as f:
            f.write(all_text)

        print(f"✅ Saved parsed text to {text_path}\n")

print("All PDFs parsed.\n")

# -----------------------------
# BASE SCHEMA
# -----------------------------
def base_schema():
    return {
        "patient_name": None,
        "patient_dob": None,
        "patient_phone": None,
        "referral_name": None,
        "provider_name": None
    }

def parse_hmgs_intake(text):
    c = base_schema()

    # --- Template Verification ---
    if "HMGS" not in text or "Dermatology" not in text:
        return c

    # --- Patient Name ---
    name_match = re.search(r"Patient Name:\s*([A-Za-z\s\-']+)", text)
    if name_match:
        name = name_match.group(1).strip()
        # Remove accidental suffix like "Date of Birth"
        name = re.sub(r"\bDate of Birth\b.*", "", name).strip()
        c["patient_name"] = name

    # --- Date of Birth ---
    dob_match = re.search(r"Date of Birth:\s*(\d{4}-\d{2}-\d{2})", text)
    if dob_match:
        c["patient_dob"] = dob_match.group(1).strip()

    # --- Patient Phone ---
    phone_match = re.search(
        r"(?:Cell Phone|Phone(?: Number)?):?\s*(?:YES\s*NO\s*YES\s*NO\s*)?(\+?\d[\d\-\(\)\s]{8,})", text
    )
    if phone_match:
        c["patient_phone"] = phone_match.group(1).strip()

    # --- Referral Name ---
    ref_match = re.search(r"Referring Physician Name:\s*(Dr\.\s*[A-Za-z\s\-']+)", text)
    if ref_match:
        referral = ref_match.group(1).strip()
        # Remove trailing "City" or extra words sometimes appended by OCR
        referral = re.sub(r"\bCity\b.*", "", referral).strip()
        c["referral_name"] = referral

    # --- Provider Name ---
    provider_match = re.search(r"Primary Care Physician Name:\s*(Dr\.\s*[A-Za-z\s\-']+)", text)
    if provider_match:
        provider = provider_match.group(1).strip()
        provider = re.sub(r"\bCity\b.*", "", provider).strip()
        c["provider_name"] = provider

    return c



def parse_stmarks_intake(text):
    """
    Parser for St. Mark's Hospital Interventional Pain Clinic intake forms.
    Returns a dictionary based on the base schema:
    {
        "patient_name": None,
        "patient_dob": None,
        "patient_phone": None,
        "referral_name": None,
        "provider_name": None
    }
    """
    c = base_schema()

    # --- Template Verification ---
    if "St. Mark" not in text and "Interventional Pain Clinic" not in text:
        return c

    # --- Patient Name ---
    name_match = re.search(r"Name:\s*([A-Za-z\s\-']+)\s+DOB:", text)
    if name_match:
        c["patient_name"] = name_match.group(1).strip()

    # --- Date of Birth ---
    dob_match = re.search(r"DOB:\s*(\d{4}-\d{2}-\d{2})", text)
    if dob_match:
        c["patient_dob"] = dob_match.group(1).strip()

    # --- Patient Phone ---
    # Prefer cell, then home/work if needed
    phone_match = re.search(r"\(C\):\s*(\+?\d[\d\-\(\)\s]{8,})", text)
    if not phone_match:
        phone_match = re.search(r"\(H\):\s*(\+?\d[\d\-\(\)\s]{8,})", text)
    if not phone_match:
        phone_match = re.search(r"\(W\):\s*(\+?\d[\d\-\(\)\s]{8,})", text)

    if phone_match:
        phone = phone_match.group(1).strip()
        # Remove trailing parentheses or partial fragments
        phone = re.sub(r"[^0-9\-\+]", "", phone)
        c["patient_phone"] = phone

    # --- Referral Name ---
    ref_match = re.search(r"Referring Physician:\s*(Dr\.\s*[A-Za-z\s\-']+)", text)
    if ref_match:
        referral = ref_match.group(1).strip()
        # Stop if a newline or new section starts
        referral = re.split(r"\n|Please list|Primary Care", referral)[0].strip()
        c["referral_name"] = referral

    # --- Provider Name ---
    provider_match = re.search(r"Primary Care Physician:\s*(Dr\.\s*[A-Za-z\s\-']+)", text)
    if provider_match:
        provider = provider_match.group(1).strip()
        # Cut off any accidental line continuation
        provider = re.split(r"\n|Please list|Referring Physician", provider)[0].strip()
        c["provider_name"] = provider

    return c


# -----------------------------
# WRAPPER
# -----------------------------
def parse_intake(text):
    """
    Detects the appropriate intake template and parses it into the base schema.
    """
    if "HMGS Dermatology" in text or "Heymann, Manders" in text:
        return parse_hmgs_intake(text)
    elif "St. Mark" in text or "Interventional Pain Clinic" in text:
        return parse_stmarks_intake(text)
    else:
        c = base_schema()
        c["error"] = "Unknown intake template"
        return c


# -----------------------------
# STEP 2: TEXT → JSON
# -----------------------------
for filename in os.listdir(parsed_text_folder):
    if not filename.endswith(".txt"):
        continue

    path = os.path.join(parsed_text_folder, filename)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Detect template & parse
    parsed = parse_intake(text)

    if "HMGS" in text:
        template = "hmgs_intake"
    elif "St. Mark" in text:
        template = "stmarks_intake"
    else:
        template = "unknown"

    out_path = os.path.join(json_output_folder, f"{os.path.splitext(filename)[0]}_{template}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2)

    print(f"✅ Parsed {filename} as {template} → {out_path}")

print("All intakes processed.")
