import pdfplumber, re, json
from io import BytesIO
from collections import OrderedDict

# ---------------- Schema normalization & ordering ----------------
def normalize_to_invoice_schema_v1(data: dict) -> OrderedDict:
    out = dict(data) if data else {}

    # account_number -> patient_id
    if 'patient_id' not in out and out.get('account_number'):
        out['patient_id'] = out.pop('account_number')
    else:
        out.pop('account_number', None)

    # strip any tax-y fields
    for k in list(out.keys()):
        if k.lower().startswith('tax'):
            out.pop(k, None)
    out.pop('tax_percent', None)
    out.pop('tax_amount', None)

    # ensure nullable fields exist (and add schema fields you asked for)
    out.setdefault('provider_name', None)
    out.setdefault('bed_id', None)
    out.setdefault('patient_phone', None)
    out.setdefault('patient_email', None)

    # preferred order
    preferred = [
        "invoice_number", "invoice_date", "due_date",
        "patient_id", "patient_name", "patient_age", "patient_address",
        "patient_phone", "patient_email",
        "admission_date", "discharge_date",
        "subtotal_amount", "discount_amount", "total_amount",
        "provider_name", "bed_id",
    ]
    ordered = OrderedDict()
    for k in preferred:
        if k in out and k != "line_items":
            ordered[k] = out[k]
    for k, v in out.items():  # any other scalars
        if k not in ordered and k != "line_items":
            ordered[k] = v
    ordered["line_items"] = out.get("line_items", [])
    return ordered

# ---------------- Preprocessing ----------------
LABEL_NORMALIZATIONS = [
    (r"Due\s+Date", "Due Date"),
    (r"Account\s*No\.?", "Account No"),
    # unify "Invoice No:" and "Invoice #" → "Invoice #"
    (r"Invoice\s*No\.?\s*:?", "Invoice #"),
    (r"Invoice\s*(#)", "Invoice #"),
    # T3: "Date of Issue" → "Invoice Date"
    (r"Date\s+of\s+Issue", "Invoice Date"),
    (r"Patient\s*Name\s*:", "Patient Name:"),
    (r"Hospital\s*No\s*:", "Hospital No:"),
    (r"Patient\s*Age\s*:", "Patient Age:"),
    (r"Admission\s*Date\s*:", "Admission Date:"),
    (r"Discharge\s*Date\s*:", "Discharge Date:"),
    (r"Sub\s*Total", "Subtotal"),
    (r"Bed\s*No\s*:", "Bed No:"),
    (r"Total\s*:\s*", "Total "),
    (r"Subtotal\s*:\s*", "Subtotal "),
]

def preprocess_text(raw: str) -> str:
    if not raw:
        return raw
    txt = raw.replace("\r", "\n")
    # stitch common wraps
    txt = re.sub(r"\$\s*\n\s*", "$", txt)
    txt = re.sub(r"(Due)\s*\n\s*(Date)", r"\1 \2", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(Account)\s*\n\s*(No\.?)", r"\1 \2", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(Invoice)\s*\n\s*(#|No\.?)", r"\1 \2", txt, flags=re.IGNORECASE)

    for pat, rep in LABEL_NORMALIZATIONS:
        txt = re.sub(pat, rep, txt, flags=re.IGNORECASE)

    # collapse excessive whitespace, keep lines
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    sentinel = " \u2028 "
    txt = txt.replace("\n", sentinel)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    txt = txt.replace(sentinel, "\n")
    txt = "\n".join(line.strip() for line in txt.splitlines())
    return txt

# ---------------- Patterns ----------------
FIELD_PATTERNS = {
    "invoice_number": re.compile(r"(?:Invoice\s*#|Invoice\s*No\.?\s*:?)\s*([A-Z0-9-]+)", re.IGNORECASE),
    "account_number": re.compile(r"Account\s*No\.?\s*([A-Z0-9-]+)", re.IGNORECASE),

    "invoice_date": re.compile(r"(?:Invoice\s*Date|Date)\s*:?\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
    "due_date": re.compile(r"Due\s*Date\s*:?\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
    "admission_date": re.compile(r"Admission\s*Date:\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
    "discharge_date": re.compile(r"Discharge\s*Date:\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),

    "patient_name": re.compile(
        r"Patient\s*Name:\s*([A-Za-z][A-Za-z\s'.-]+?)(?:\s*Hospital\s*No:|\n[A-Z][a-z]+[:])",
        re.IGNORECASE
    ),
    "patient_age": re.compile(r"Patient\s*Age:\s*(\d+)\b", re.IGNORECASE),

    # Address: labeled form (T1/T2). T3 handled by BILLED TO block (see below).
    "patient_address": re.compile(
        r"Address:\s*(.+?)\s*(?:Admission\s*Date|Discharge\s*Date|Subtotal|Total|Due\s*Date|Invoice\s*Date|Phone|Email|E:|Contact|INVOICE\s*DETAILS)",
        re.IGNORECASE | re.DOTALL
    ),

    "subtotal_amount": re.compile(r"^\s*Subtotal\b[: ]\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE | re.MULTILINE),
    "discount_amount": re.compile(r"^\s*Discount\b[: ]\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE | re.MULTILINE),
    "total_amount": re.compile(r"^\s*Total\b[: ]\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE | re.MULTILINE),
}

PHONE_RE = re.compile(r"(?:\+?\d{1,2}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

SUMMARY_DESC = {"subtotal", "sub total", "discount", "total", "tax", "tax rate"}
CODE_RE = re.compile(r"^[A-Z]{1,4}\d{2,4}$")  # LP12, CT15, EE09, HT02, etc.

# ---------------- Helpers ----------------
def clean_and_convert(key, value):
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip().replace(",", "")
    if key in {"subtotal_amount","discount_amount","total_amount","amount"}:
        try:
            return float(re.sub(r"[^\d.]", "", cleaned))
        except ValueError:
            return None
    if key == "patient_age":
        try:
            return int(float(cleaned))
        except ValueError:
            return None
    return cleaned

def sanitize_code_cell(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9-]", "", (s or "").strip())

def extract_fields(prepped_text: str) -> dict:
    data = {}
    for key, pat in FIELD_PATTERNS.items():
        m = pat.search(prepped_text)
        data[key] = clean_and_convert(key, m.group(1)) if m else None

    # phone/email anywhere (footer in T3)
    phones = PHONE_RE.findall(prepped_text or "")
    emails = EMAIL_RE.findall(prepped_text or "")
    if phones:
        data["patient_phone"] = phones[0]
    if emails:
        data["patient_email"] = emails[0]
    return data

def _looks_like_name(s: str) -> bool:
    if not s: return False
    if len(s) > 60: return False
    if re.search(r"\d|@", s): return False
    words = s.strip().split()
    if len(words) < 2 or len(words) > 7: return False
    titleish = sum(1 for w in words if re.match(r"[A-Z][a-z'.-]+\.?$", w))
    return titleish >= max(2, len(words) - 1)

def _patient_name_fallback(prepped_text: str) -> str | None:
    # For T2/T3 when "Patient Name:" absent and no BILLED TO (handled below)
    lines = [ln.strip() for ln in prepped_text.splitlines() if ln.strip()]
    for ln in lines[:15]:
        if re.search(r"\b(invoice|clinic|hospital|address|phone|email|website|due|date|account|subtotal|total|tax|code|description|particulars)\b", ln, re.I):
            continue
        if _looks_like_name(ln):
            return ln
    return None

def _extract_billed_to(prepped_text: str):
    """
    T3: Parse the 'BILLED TO:' block. First non-empty line → name,
    subsequent non-empty lines until a stop token → address.
    """
    lines = prepped_text.splitlines()
    name, addr_lines = None, []
    grabbing = False
    for ln in lines:
        s = ln.strip()
        if not grabbing:
            if re.search(r"\bBILLED\s*TO\s*:\s*$", s, flags=re.I) or re.search(r"\bBILLED\s*TO\s*:\s*", s, flags=re.I):
                grabbing = True
                # if it has inline text like "BILLED TO: John", split and start name
                after = re.sub(r".*BILLED\s*TO\s*:\s*", "", s, flags=re.I).strip()
                if after:
                    name = after
                continue
        else:
            if not s:
                break
            if re.search(r"\bINVOICE\s*DETAILS\b|\bInvoice\s*#|\bInvoice\s*Date\b|\bDue\s*Date\b", s, re.I):
                break
            if name is None:
                name = s
            else:
                addr_lines.append(s)
    address = " ".join(addr_lines).strip() if addr_lines else None
    return name, address

def _is_summary_row(desc: str, code: str) -> bool:
    d = (desc or "").strip().lower()
    c = (code or "").strip().lower()
    if d in SUMMARY_DESC or c in SUMMARY_DESC:
        return True
    if d.endswith(":") and d[:-1].strip().lower() in SUMMARY_DESC:
        return True
    return False

# ---------------- Line items (T1 + T2 + T3) ----------------
def extract_line_items(first_page, prepped_text: str) -> list:
    items = []

    # 1) Try pdfplumber tables (good for T1; sometimes T3 prints a header row)
    try:
        tables = first_page.extract_tables(
            table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"}
        )
        for table in tables or []:
            if not table or not table[0]:
                continue
            header = [ (c or "").strip().lower() for c in table[0] ]

            def find_idx(candidates):
                for c in candidates:
                    if c in header:
                        return header.index(c)
                return None

            idx_code = find_idx(["code"])
            idx_desc = find_idx(["particulars", "description", "item", "service"])
            idx_amt  = find_idx(["amount", "price", "total"])

            if idx_amt is None:
                continue

            for row in table[1:]:
                if not row: 
                    continue
                cells = [(c or "").strip() for c in row]
                code = sanitize_code_cell(cells[idx_code]) if idx_code is not None and idx_code < len(cells) else None
                desc = (cells[idx_desc] if idx_desc is not None and idx_desc < len(cells) else None) or ""
                amt_raw = cells[idx_amt] if idx_amt < len(cells) else ""
                m_amt = re.search(r"([\d,]+\.\d{2})", amt_raw)
                amt = clean_and_convert("amount", m_amt.group(1)) if m_amt else None

                if _is_summary_row(desc, code):
                    continue
                if not code or not CODE_RE.fullmatch(code):
                    # try to find a code-looking cell elsewhere in the row
                    for c in cells:
                        cand = sanitize_code_cell(c)
                        if CODE_RE.fullmatch(cand):
                            code = cand
                            break
                if not code or not CODE_RE.fullmatch(code):
                    continue
                if not desc:
                    cand_desc = [c for c in cells if re.search(r"\d", c) is None and not CODE_RE.fullmatch(sanitize_code_cell(c))]
                    if cand_desc:
                        desc = max(cand_desc, key=len)
                if desc and amt is not None and code:
                    items.append({"code": code, "description": desc.strip(), "amount": amt})
    except Exception:
        pass

    # 2) Text fallbacks — T1/T3 (code first) and T2 (desc first)
    # We scan the WHOLE text so it works even if totals come first (T3).
    if not items:
        for m in re.finditer(
            r"^(?!\s*(?:Sub\s*Total|Subtotal|Discount|Total|Tax(?:\s*Rate)?)\b)"
            r"([A-Z]{1,4}\d{2,4})\s+(.+?)\s+\$?([\d,]+\.\d{2})$",
            prepped_text, flags=re.MULTILINE):
            code, desc, amt = m.groups()
            items.append({"code": code, "description": desc.strip(),
                          "amount": clean_and_convert("amount", amt)})

    if not items:
        for m in re.finditer(
            r"^(?!\s*(?:Sub\s*Total|Subtotal|Discount|Total|Tax(?:\s*Rate)?)\b)"
            r"(.+?)\s+([A-Z]{1,4}\d{2,4})\s+\$?([\d,]+\.\d{2})$",
            prepped_text, flags=re.MULTILINE):
            desc, code, amt = m.groups()
            if re.search(r"\bdescription\b.*\bcode\b", desc, flags=re.I):
                continue
            items.append({"code": code, "description": desc.strip(),
                          "amount": clean_and_convert("amount", amt)})

    return items

# ---------------- Parse orchestration ----------------
def parse_invoice(prepped_text: str, page) -> dict:
    data = extract_fields(prepped_text)

    # BILLED TO (T3): if we don't already have a labeled patient_name/address
    if not data.get("patient_name") or not data.get("patient_address"):
        bt_name, bt_addr = _extract_billed_to(prepped_text)
        if bt_name and not data.get("patient_name"):
            data["patient_name"] = bt_name
        if bt_addr and not data.get("patient_address"):
            data["patient_address"] = bt_addr

    # unlabeled name fallback (T2/T3)
    if not data.get("patient_name"):
        pn = _patient_name_fallback(prepped_text)
        if pn:
            data["patient_name"] = pn

    # due_date heuristic if missing
    if not data.get("due_date"):
        lines = prepped_text.splitlines()
        header = []
        for line in lines:
            header.append(line)
            if "Patient Details" in line or "INVOICE DETAILS" in line.upper():
                break
        dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", "\n".join(header))
        inv = data.get("invoice_date")
        if inv and inv in dates and len(dates) > 1:
            data["due_date"] = next((d for d in dates if d != inv), None)
        elif len(dates) >= 2:
            data["due_date"] = dates[1]

    # line items
    data["line_items"] = extract_line_items(page, prepped_text)

    # final defensive cleanup
    for k in list(data.keys()):
        if k.lower().startswith("tax"):
            data.pop(k, None)

    return data

def parse_pdf_bytes(pdf_bytes: bytes) -> dict:
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[0]
            raw_text = page.extract_text()
            if not raw_text:
                return {"error": "Could not extract text from PDF."}
            prepped = preprocess_text(raw_text)
            parsed = parse_invoice(prepped, page)
            return normalize_to_invoice_schema_v1(parsed)
    except Exception as e:
        return {"error": f"An unexpected error occurred during PDF processing: {e}"}
