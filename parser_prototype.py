import pdfplumber, re, json
from io import BytesIO
from collections import OrderedDict
from datetime import datetime, date, timedelta

# ---------------- Schema normalization & ordering ----------------
def normalize_to_invoice_schema_v1(data: dict) -> OrderedDict:
    out = dict(data) if data else {}

    # account_number -> patient_id
    if 'patient_id' not in out and out.get('account_number'):
        out['patient_id'] = out.pop('account_number')
    else:
        out.pop('account_number', None)

    # drop tax-ish keys defensively
    for k in list(out.keys()):
        if k.lower().startswith('tax'):
            out.pop(k, None)
    out.pop('tax_percent', None)
    out.pop('tax_amount', None)

    # ensure nullable keys exist
    out.setdefault('provider_name', None)
    out.setdefault('bed_id', None)
    out.setdefault('patient_phone', None)
    out.setdefault('patient_email', None)

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
    for k, v in out.items():
        if k not in ordered and k != "line_items":
            ordered[k] = v
    ordered["line_items"] = out.get("line_items", [])
    return ordered

# ---------------- Label normalizations ----------------
LABEL_NORMALIZATIONS = [
    (r"Due\s+Date", "Due Date"),
    (r"Account\s*No\.?", "Account No"),
    (r"Invoice\s*No\.?\s*:?", "Invoice #"),
    (r"Invoice\s*(#)", "Invoice #"),
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
    (r"Consultant\s*:", "Consultant:"),
]

# -------- Common helpers for address stitching in preprocessing (T1) --------
CITY_ZIP_RE = re.compile(r"\b[A-Z]{2}\s*\d{5}(?:-\d{4})?\b")
NEXT_LABEL_HEADS = re.compile(
    r"^(Admission|Discharge|Patient\s*Age|Hospital\s*No|Bed\s*No|Consultant|Phone|Email|Subtotal|Sub\s*Total|Total|Due\s*Date|Invoice\s*Date|Code\b|Invoice\s*Details|Tax\b)\b",
    re.IGNORECASE
)

def _stitch_T1_address_lines(lines):
    """
    T1 quirk:
      prev line: street
      line with "Address:" might be polluted
      next line: city, ST ZIP
    We'll fuse prev + next into the "Address:" line.
    """
    for i, line in enumerate(lines):
        if not re.search(r"\bAddress\s*:", line, flags=re.IGNORECASE):
            continue

        prev_line = lines[i-1].strip() if i - 1 >= 0 else ""
        next_line = lines[i+1].strip() if i + 1 < len(lines) else ""

        prev_ok = bool(prev_line) and (":" not in prev_line) and not NEXT_LABEL_HEADS.match(prev_line)
        next_ok = bool(next_line) and (CITY_ZIP_RE.search(next_line) or not NEXT_LABEL_HEADS.match(next_line))

        if prev_ok and next_ok:
            combined = f"Address: {prev_line}, {next_line}"
            lines[i] = combined
            lines[i-1] = ""
            lines[i+1] = ""
            break
    return lines

# ---------------- Template detection ----------------
def detect_template(txt: str) -> str | None:
    """
    Returns "T1", "T2", "T3", or None
    """
    t = txt.lower() if txt else ""
    if "hot springs general hospital" in t:
        return "T1"
    if "rose petal clinic" in t:
        return "T2"
    if "white petal hospital center" in t:
        return "T3"
    return None

# ---------------- Preprocessing (template-specific) ----------------
def _base_label_cleanup(txt: str) -> str:
    # normalize label variants
    for pat, rep in LABEL_NORMALIZATIONS:
        txt = re.sub(pat, rep, txt, flags=re.IGNORECASE)
    return txt

def _collapse_layout_keep_lines(txt: str) -> str:
    """
    Generic cleanup we apply at the end of each template preprocessor:
    - get rid of huge blank regions
    - collapse excess spaces
    - but keep line breaks meaningful
    """
    txt = re.sub(r"\n{3,}", "\n\n", txt)

    # temporarily mark newlines so we can collapse spaces safely
    sentinel = " \u2028 "
    txt = txt.replace("\r", "\n")
    txt = txt.replace("\n", sentinel)

    # collapse runs of tabs/spaces
    txt = re.sub(r"[ \t]{2,}", " ", txt)

    # restore newlines
    txt = txt.replace(sentinel, "\n")

    # trim each line
    txt = "\n".join(line.strip() for line in txt.splitlines())
    return txt

def _extract_first_dates_from_raw(raw: str):
    """
    For admission/discharge. Used mainly for T1.
    """
    adm_match = re.search(
        r"Admission\s*Date\s*:\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
        raw or "",
        flags=re.IGNORECASE
    )
    dis_match = re.search(
        r"Discharge\s*Date\s*:\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
        raw or "",
        flags=re.IGNORECASE
    )
    return (
        adm_match.group(1) if adm_match else None,
        dis_match.group(1) if dis_match else None
    )

def _preprocess_T1(raw: str):
    """
    Hot Springs General Hospital
    We do:
    - capture admission/discharge FROM RAW
    - stitch split labels (Admission / Date, etc.)
    - stitch "$\n430.00" money breaks
    - stitch T1 3-line address trick
    - normalize labels
    - collapse whitespace (keep lines)
    """
    if not raw:
        return "", None, None

    # grab dates before we mutate text
    admission_date_raw, discharge_date_raw = _extract_first_dates_from_raw(raw)

    txt = raw.replace("\r", "\n")

    # stitch "$\n430.00" -> "$430.00"
    txt = re.sub(r"\$\s*\n\s*", "$", txt)

    # fix label linewraps specific to T1 layout
    def stitch(a, b):
        nonlocal txt
        txt = re.sub(fr"({a})\s*(?:\n|\r)+\s*({b})",
                     r"\1 \2",
                     txt,
                     flags=re.IGNORECASE)

    stitch("Due", "Date")
    stitch("Account", r"No\.?")
    stitch("Invoice", r"#|No\.?")
    stitch("Admission", "Date")
    stitch("Discharge", "Date")
    stitch("Bed", r"No\.?")
    stitch("Hospital", r"No\.?")
    stitch("Patient", r"Name:?")

    # weird split in "Date:" -> "Da\nte:"
    txt = re.sub(r"(Da)te\s*:\s*", r"\1te: ", txt, flags=re.IGNORECASE)

    # normalize labels
    txt = _base_label_cleanup(txt)

    # stitch T1 tri-line address BEFORE big whitespace collapse
    lines = [ln.rstrip() for ln in txt.split("\n")]
    lines = _stitch_T1_address_lines(lines)
    txt = "\n".join(lines)

    # final collapse / cleanup
    txt = _collapse_layout_keep_lines(txt)

    return txt, admission_date_raw, discharge_date_raw

def _preprocess_T2(raw: str):
    """
    Rose Petal Clinic.
    Observations (from sample):
      - No admission/discharge dates at all.
      - A lot of 'Invoice No:', 'Date:', 'Due Date:' inline already.
      - Contact block repeats clinic phone/email after patient phone/email.
    We'll:
      - keep same stitching for $, invoice/date/due date
      - normalize labels
      - collapse layout.
    We don't try fancy address stitching since T2 already has 'Address:' line.
    """
    if not raw:
        return "", None, None

    admission_date_raw = None
    discharge_date_raw = None

    txt = raw.replace("\r", "\n")

    # stitch "$\n2325.00" etc.
    txt = re.sub(r"\$\s*\n\s*", "$", txt)

    # Some templates break "Due" and "Date" etc.
    def stitch(a, b):
        nonlocal txt
        txt = re.sub(fr"({a})\s*(?:\n|\r)+\s*({b})",
                     r"\1 \2",
                     txt,
                     flags=re.IGNORECASE)

    stitch("Due", "Date")
    stitch("Invoice", r"#|No\.?")
    stitch("Date", r":")  # in case "Date" and ":" are split
    # T2 doesn't have Admission/Discharge, Bed/Hospital, etc., but harmless if present.

    # cleanup "Da\nte:" weirdness just in case
    txt = re.sub(r"(Da)te\s*:\s*", r"\1te: ", txt, flags=re.IGNORECASE)

    # normalize labels ("Invoice No:" -> "Invoice #", etc.)
    txt = _base_label_cleanup(txt)

    # final spacing collapse but keep lines
    txt = _collapse_layout_keep_lines(txt)

    return txt, admission_date_raw, discharge_date_raw

def _preprocess_T3(raw: str):
    """
    White Petal Hospital Center.
    Observations (from sample):
      - Has "BILLED TO:" then name + address in multiple lines.
      - Has "Date of Issue" (becomes Invoice Date).
      - Has "Due Date".
      - No Admission/Discharge in sample.
    We'll:
      - stitch "$" lines
      - join any broken "Invoice", "Due Date", etc.
      - normalize labels (so 'Date of Issue' -> 'Invoice Date')
      - collapse layout.
    """
    if not raw:
        return "", None, None

    admission_date_raw = None
    discharge_date_raw = None

    txt = raw.replace("\r", "\n")

    # stitch "$\n1435.00" -> "$1435.00"
    txt = re.sub(r"\$\s*\n\s*", "$", txt)

    def stitch(a, b):
        nonlocal txt
        txt = re.sub(fr"({a})\s*(?:\n|\r)+\s*({b})",
                     r"\1 \2",
                     txt,
                     flags=re.IGNORECASE)

    stitch("Due", "Date")
    stitch("Invoice", r"#|No\.?")
    stitch("Date", r"of")  # e.g. "Date \n of Issue"
    stitch("of", r"Issue")
    stitch("BILLED", r"TO")

    # cleanup "Da\nte:" just in case
    txt = re.sub(r"(Da)te\s*:\s*", r"\1te: ", txt, flags=re.IGNORECASE)

    # normalize labels globally for this text
    txt = _base_label_cleanup(txt)

    # final collapse / cleanup
    txt = _collapse_layout_keep_lines(txt)

    return txt, admission_date_raw, discharge_date_raw

# ---------------- Date handling ----------------
DATE_TOKEN = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})"

def _parse_date(s: str):
    s = s.strip()
    fmts = [
        "%Y-%m-%d",
        "%m/%d/%Y","%m/%d/%y",
        "%d/%m/%Y","%d/%m/%y",
        "%d %b %Y","%d %B %Y"
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date()
        except Exception:
            pass
    return None

def norm_date(s: str) -> str | None:
    d = _parse_date(s) if s else None
    return d.isoformat() if d else None

# ---------------- Patterns ----------------
FIELD_PATTERNS = {
    "invoice_number": re.compile(
        r"(?:Invoice\s*#|Invoice\s*No\.?\s*:?)\s*([A-Z0-9_/-]+)",
        re.IGNORECASE
    ),
    "account_number": re.compile(
        r"Account\s*No\.?\s*([A-Z0-9_/-]+)",
        re.IGNORECASE
    ),

    "invoice_date": re.compile(
        r"(?:Invoice\s*Date|Date)\s*:?\s*" + DATE_TOKEN,
        re.IGNORECASE
    ),
    "due_date": re.compile(
        r"(?:Due\s*Date|Payment\s*Due|Due\s*by|Terms?:?.{0,30}?Due)\s*[:\-\u2013]?\s*(?:\n|\r|\s){0,50}" + DATE_TOKEN,
        re.IGNORECASE
    ),

    "admission_date": re.compile(
        r"Admission\s*Date:\s*" + DATE_TOKEN,
        re.IGNORECASE
    ),
    "discharge_date": re.compile(
        r"Discharge\s*Date:\s*" + DATE_TOKEN,
        re.IGNORECASE
    ),

    "patient_name": re.compile(
        r"Patient\s*Name:\s*([^\n]+?)(?=\s*(?:Hospital\s*No:|Patient\s*Age:|Bed\s*No:|Admission\s*Date:|Discharge\s*Date:|Address:|Subtotal|Total|Due\s*Date|Invoice\s*Date|Phone|Email|Consultant:|INVOICE\s*DETAILS|Code|$))",
        re.IGNORECASE
    ),
    "patient_age": re.compile(
        r"Patient\s*Age:\s*(\d+)\b",
        re.IGNORECASE
    ),

    # generic address fallback (templates may override)
    "patient_address": re.compile(
        r"Address:\s*(.+?)\s*(?=(?:Patient\s*Age|Hospital\s*No|Bed\s*No|Consultant|Admission\s*Dat(?:e)?|Discharge\s*Dat(?:e)?|Subtotal|Total|Due\s*Date|Invoice\s*Date|Phone|Email|E:|Contact|INVOICE\s*DETAILS|Code|$))",
        re.IGNORECASE | re.DOTALL
    ),

    "bed_id": re.compile(
        r"Bed\s*No\s*:\s*([A-Z0-9_-]+)",
        re.IGNORECASE
    ),
    "provider_name": re.compile(
        r"(?:Consultant|Provider|Doctor)\s*:\s*([^\n:][^\n]+?)\s*(?=(?:Bed\s*No|Phone|Email|Address|Admission\s*Date|Discharge\s*Date|Subtotal|Total|$))",
        re.IGNORECASE
    ),

    "subtotal_amount": re.compile(
        r"^\s*Subtotal\b[: ]\s*\$?([\d,]+(?:\.\d{2})?)",
        re.IGNORECASE | re.MULTILINE
    ),
    "discount_amount": re.compile(
        r"^\s*Discount\b[: ]\s*\$?([\d,]+(?:\.\d{2})?)",
        re.IGNORECASE | re.MULTILINE
    ),
    "total_amount": re.compile(
        r"^\s*Total\b[: ]\s*\$?([\d,]+(?:\.\d{2})?)",
        re.IGNORECASE | re.MULTILINE
    ),
}

# Phone & Email regexes
PHONE_RE = re.compile(
    r"(?:\+?\d{1,2}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
EMAIL_LABELED_RE = re.compile(
    r"(?:Email|E:)\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE
)
EMAIL_ANY_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE
)

SUMMARY_DESC = {
    "subtotal",
    "sub total",
    "discount",
    "total",
    "tax",
    "tax rate"
}
CODE_RE = re.compile(r"^[A-Z]{1,4}-?\d{2,4}$")

# ---------------- Template-specific address extractors (textual) ----------------
def extract_address_T1(txt: str) -> str | None:
    # In T1, Address: may be followed by bed/admission junk on same line,
    # then the city/state next line.
    m = re.search(r"Address\s*:\s*(.*)$", txt, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    line1 = (m.group(1) or "").strip()
    rest = txt[m.end():]
    line2 = ""
    if rest:
        lines = rest.splitlines()
        if lines:
            line2 = lines[0].strip()
    joined = ", ".join([p for p in [line1, line2] if p])
    joined = re.sub(
        r"\b(Admission\s*Date|Discharge\s*Date|Patient\s*Age|Hospital\s*No|Bed\s*No|Consultant|Phone|Email)\b.*$",
        "",
        joined,
        flags=re.IGNORECASE,
    )
    joined = re.sub(r"[.\u2024\u2027\u2219\u22C5\u00B7]{2,}", " ", joined)
    joined = re.sub(r"\s{2,}", " ", joined).strip(" ,;:-")
    return joined or None

def extract_address_T2(txt: str) -> str | None:
    # In T2, Address: is already clean: "Address: 4117 Cedarstone Drive, Amherst NH, 03031"
    m = re.search(r"\bAddress\s*:\s*(.+)$", txt, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    addr = m.group(1).strip()
    addr = re.sub(r"\s{2,}", " ", addr).strip(" ,;:-")
    return addr or None

def extract_address_T3(txt: str) -> str | None:
    # T3 puts address under BILLED TO:
    # BILLED TO: Name
    # street line
    # city/state/zip line
    lines = txt.splitlines()
    grabbing = False
    name_seen = False
    addr_lines = []
    for ln in lines:
        s = ln.strip()
        if not grabbing:
            if re.search(r"\bBILLED\s*TO\s*:\s*$", s, flags=re.I) or \
               re.search(r"\bBILLED\s*TO\s*:\s*", s, flags=re.I):
                grabbing = True
                after = re.sub(r".*BILLED\s*TO\s*:\s*", "", s, flags=re.I).strip()
                if after:
                    # The line that has "BILLED TO:" ALSO includes the name sometimes.
                    name_seen = True
                continue
        else:
            if not s:
                break
            # stop if we hit invoice details section
            if re.search(r"\bINVOICE\s*DETAILS\b|\bInvoice\s*#|\bInvoice\s*Date\b|\bDue\s*Date\b", s, re.I):
                break
            # first line after "BILLED TO:" is probably the name if we didn't
            # see it inline yet
            if not name_seen:
                name_seen = True
                continue
            addr_lines.append(s)
            if len(addr_lines) >= 2:
                break

    addr = ", ".join(addr_lines).strip(" ,;:-")
    return addr or None

def extract_patient_address_by_template(txt: str, template: str) -> str | None:
    if template == "T1":
        return extract_address_T1(txt)
    if template == "T2":
        return extract_address_T2(txt)
    if template == "T3":
        return extract_address_T3(txt)

    # fallback: generic regex slice
    m = FIELD_PATTERNS["patient_address"].search(txt)
    if m:
        addr = m.group(1)
        addr = re.sub(r"[.\u2024\u2027\u2219\u22C5\u00B7]{2,}", " ", addr)
        addr = re.sub(r"\s{2,}", " ", addr).strip(" ,;:-")
        return addr or None
    return None

# ---------------- Spatial address extraction for T1 ----------------
def _group_words_by_line(words, tolerance=2.0):
    lines = []
    # sort words by vertical position, then x
    for w in sorted(words, key=lambda x: (round(w["top"], 1), w["x0"])):
        y = w["top"]
        if not lines or abs(lines[-1]["y"] - y) > tolerance:
            lines.append({"y": y, "words": [w]})
        else:
            lines[-1]["words"].append(w)
    for ln in lines:
        ln["words"].sort(key=lambda x: x["x0"])
    return lines

def _find_label_token_idx(line_words, label="address"):
    for i, w in enumerate(line_words):
        t = w["text"].strip().lower()
        if t in (label, f"{label}:"):
            return i
    return -1

def extract_address_T1_spatial(page) -> str | None:
    """
    Geometric fallback for T1 if text address extraction fails / is messy.
    """
    words = page.extract_words() or []
    if not words:
        return None
    lines = _group_words_by_line(words)
    addr_line_idx = None
    addr_token_idx = None
    for idx, ln in enumerate(lines):
        i = _find_label_token_idx(ln["words"], label="address")
        if i >= 0:
            addr_line_idx = idx
            addr_token_idx = i
            break
    if addr_line_idx is None:
        return None

    # Everything to the right of "Address:"
    same_line_words = lines[addr_line_idx]["words"][addr_token_idx + 1 :]
    line1_val = " ".join(w["text"] for w in same_line_words).strip()

    # maybe next one or two physical lines are continuation
    follow_vals = []
    for ln in lines[addr_line_idx + 1 : addr_line_idx + 3]:
        candidate = " ".join(w["text"] for w in ln["words"]).strip()
        if not candidate or NEXT_LABEL_HEADS.match(candidate):
            break
        follow_vals.append(candidate)

    parts = [p for p in [line1_val] + follow_vals if p]
    if not parts:
        return None

    addr = ", ".join(parts)

    # scrub trailing labels
    addr = re.sub(r"[.\u2024\u2027\u2219\u22C5\u00B7]{2,}", " ", addr)
    addr = re.sub(
        r"\b(Admission\s*Date|Discharge\s*Date|Patient\s*Age|Hospital\s*No|Bed\s*No|Consultant|Phone|Email)\b.*$",
        "",
        addr,
        flags=re.IGNORECASE
    )
    addr = re.sub(r"\s{2,}", " ", addr).strip(" ,;:-")
    if not addr or addr.lower().startswith("admission"):
        return None

    return addr or None

# ---------------- Helpers ----------------
def clean_and_convert(key, value):
    if value is None:
        return None
    s = str(value)
    if key in {"invoice_date", "due_date", "admission_date", "discharge_date"}:
        return norm_date(s)

    cleaned = re.sub(r"\s+", " ", s).strip().replace(",", "")
    if key in {"subtotal_amount", "discount_amount", "total_amount", "amount"}:
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

def _slice_patient_block(txt: str) -> str:
    """
    Capture likely patient info region, starting at 'Patient Name:' or 'Address:'
    and ending before big table / invoice details.
    """
    start = None
    for pat in [r"Patient\s*Name:", r"Address:"]:
        m = re.search(pat, txt, re.IGNORECASE)
        if m:
            start = m.start() if start is None else min(start, m.start())
    if start is None:
        return ""

    end_pat = re.compile(
        r"(?:Admission\s*Date:|Discharge\s*Date:|INVOICE\s*DETAILS|^\s*Code\s*$|Code\s+Description)",
        re.IGNORECASE | re.MULTILINE
    )
    m_end = end_pat.search(txt[start:])
    end = start + m_end.start() if m_end else len(txt)
    return txt[start:end]

# --------------- Post-extraction normalizers ----------------
def _collapse_ws(s: str | None) -> str | None:
    if not s:
        return s
    return re.sub(r"\s+", " ", s).strip()

def _normalize_us_phone(s: str | None) -> str | None:
    """
    Normalize to NNN-NNN-NNNN:
    - strip non-digits
    - keep LAST 10 digits (to drop +1, etc.)
    """
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 10:
        last10 = digits[-10:]
        return f"{last10[0:3]}-{last10[3:6]}-{last10[6:10]}"
    return digits if len(digits) >= 7 else None

US_CITY_STATE_ZIP = re.compile(
    r"^\s*([A-Za-z .'-]+)\s*,?\s*([A-Z]{2})\s*,?\s*(\d{5}(?:-\d{4})?)\s*$"
)

def _normalize_us_address(addr: str | None) -> str | None:
    if not addr:
        return addr

    # collapse newlines -> ", "
    a = addr.replace("\n", ", ")
    a = re.sub(r"\s+", " ", a).strip(" ,;")

    # "street, rest"
    m = re.match(r"^(.*?),(.*)$", a)
    if m:
        street = m.group(1).strip()
        rest   = m.group(2).strip()
        m2 = US_CITY_STATE_ZIP.match(rest)
        if m2:
            city, st, z = m2.groups()
            return f"{street}, {city.strip()}, {st} {z}"
        # else try to clean comma before ZIP etc.
        rest = re.sub(r",\s*(\d{5}(?:-\d{4})?)$", r" \1", rest)
        rest = re.sub(
            r"([A-Za-z])\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
            r"\1, \2 \3",
            rest
        )
        return f"{street}, {rest}".strip(" ,;")

    # "street City ST ZIP"
    m3 = re.match(
        r"^(.*)\s+([A-Za-z .'-]+)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
        a
    )
    if m3:
        street, city, st, z = m3.groups()
        return f"{street.strip()}, {city.strip()}, {st} {z}"

    # final touchups
    a = re.sub(r",\s*(\d{5}(?:-\d{4})?)$", r" \1", a)
    a = re.sub(
        r"([A-Za-z])\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
        r"\1, \2 \3",
        a
    )
    return a

def _postprocess_uniformity(data: dict) -> dict:
    """
    Standardize:
    - collapse whitespace in stringy fields
    - address -> "Street, City, ST 00000"
    - phone   -> "NNN-NNN-NNNN"
    """
    for k in [
        "invoice_number", "patient_name", "patient_address",
        "provider_name", "bed_id", "patient_email"
    ]:
        if k in data and isinstance(data[k], str):
            data[k] = _collapse_ws(data[k])

    if data.get("patient_address"):
        data["patient_address"] = _normalize_us_address(data["patient_address"])

    if data.get("patient_phone"):
        data["patient_phone"] = _normalize_us_phone(data["patient_phone"])

    return data

# ---------------- Field extraction ----------------
def extract_fields(prepped_text: str) -> dict:
    data = {}
    for key, pat in FIELD_PATTERNS.items():
        m = pat.search(prepped_text)
        if not m:
            data[key] = None
            continue
        grp = m.groups()[-1] if m.groups() else None
        data[key] = clean_and_convert(key, grp)

    # slice likely patient block once
    patient_blk = _slice_patient_block(prepped_text)

    # ----- EMAIL with blacklist -----
    email_val = None
    m_email = EMAIL_LABELED_RE.search(patient_blk)
    if m_email:
        email_val = m_email.group(1).strip()
    else:
        m_email2 = EMAIL_LABELED_RE.search(prepped_text)
        if m_email2:
            email_val = m_email2.group(1).strip()
        else:
            m_any = EMAIL_ANY_RE.search(prepped_text)
            email_val = m_any.group(0).strip() if m_any else None

    EMAIL_BLACKLIST = {"info@hotspringsgen.com"}
    if email_val and email_val.lower() in EMAIL_BLACKLIST:
        email_val = None

    data["patient_email"] = email_val

    # ----- PHONE with blacklist -----
    m_phone_labeled = re.search(
        r"(?:Phone|Tel|Contact)\s*[:\-]?\s*(" + PHONE_RE.pattern + ")",
        patient_blk,
        re.IGNORECASE
    )
    if m_phone_labeled:
        phone_val = m_phone_labeled.group(1).strip()
    else:
        phones = PHONE_RE.findall(prepped_text or "")
        if phones:
            if isinstance(phones[0], str):
                phone_val = phones[0].strip()
            else:
                phone_val = phones[0][0].strip()
        else:
            phone_val = None

    if phone_val:
        digits = re.sub(r"\D", "", phone_val)
        last10 = digits[-10:] if len(digits) >= 10 else digits
        if last10 == "1234567890":
            phone_val = None

    data["patient_phone"] = phone_val

    # ----- ADDRESS -----
    template = detect_template(prepped_text)
    addr = extract_patient_address_by_template(prepped_text, template)
    if addr:
        data["patient_address"] = addr

    # standardize before returning
    return _postprocess_uniformity(data)

# ---------------- Patient name fallbacks ----------------
def _looks_like_name(s: str) -> bool:
    if not s:
        return False
    if len(s) > 60:
        return False
    if re.search(r"\d|@", s):
        return False
    words = s.strip().split()
    if len(words) < 2 or len(words) > 7:
        return False
    titleish = sum(
        1 for w in words if re.match(r"[A-Z][a-z'.-]+\.?$", w)
    )
    return titleish >= max(2, len(words) - 1)

def _patient_name_fallback(prepped_text: str) -> str | None:
    lines = [ln.strip() for ln in prepped_text.splitlines() if ln.strip()]
    for ln in lines[:15]:
        if re.search(
            r"\b(invoice|clinic|hospital|address|phone|email|website|due|date|account|subtotal|total|tax|code|description|particulars|billed\s*to)\b",
            ln,
            re.I
        ):
            continue
        if _looks_like_name(ln):
            return ln
    return None

def _extract_billed_to(prepped_text: str):
    """
    Used mainly by T3:
    tries to read the block after 'BILLED TO:' to get name and address lines.
    """
    lines = prepped_text.splitlines()
    name, addr_lines = None, []
    grabbing = False
    for ln in lines:
        s = ln.strip()
        if not grabbing:
            if re.search(r"\bBILLED\s*TO\s*:\s*$", s, flags=re.I) or \
               re.search(r"\bBILLED\s*TO\s*:\s*", s, flags=re.I):
                grabbing = True
                after = re.sub(
                    r".*BILLED\s*TO\s*:\s*",
                    "",
                    s,
                    flags=re.I
                ).strip()
                if after:
                    name = after
                continue
        else:
            if not s:
                break
            if re.search(
                r"\bINVOICE\s*DETAILS\b|\bInvoice\s*#|\bInvoice\s*Date\b|\bDue\s*Date\b",
                s,
                re.I
            ):
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

# ---------------- Line items ----------------
def extract_line_items(first_page, prepped_text: str) -> list:
    items = []
    try:
        tables = first_page.extract_tables(
            table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"}
        )
        for table in tables or []:
            if not table or not table[0]:
                continue

            header = [(c or "").strip().lower() for c in table[0]]

            def find_idx(cands):
                for c in cands:
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

                code = sanitize_code_cell(cells[idx_code]) \
                       if idx_code is not None and idx_code < len(cells) else None
                desc = (cells[idx_desc] if idx_desc is not None and idx_desc < len(cells) else None) or ""
                amt_raw = cells[idx_amt] if idx_amt < len(cells) else ""

                m_amt = re.search(r"([\d,]+\.\d{2})", amt_raw)
                amt = clean_and_convert("amount", m_amt.group(1)) if m_amt else None

                # skip subtotal/discount/total rows
                if _is_summary_row(desc, code):
                    continue

                # recover code if parser couldn't
                if (not code) or (not CODE_RE.fullmatch(code)):
                    for c in cells:
                        cand = sanitize_code_cell(c)
                        if CODE_RE.fullmatch(cand):
                            code = cand
                            break

                # recover description if blank
                if not desc:
                    cand_desc = [
                        c for c in cells
                        if re.search(r"\d", c) is None
                        and not CODE_RE.fullmatch(sanitize_code_cell(c))
                    ]
                    if cand_desc:
                        desc = max(cand_desc, key=len)

                # actually add the item
                if desc and amt is not None and (code is None or CODE_RE.fullmatch(code)):
                    items.append(OrderedDict([
                        ("description", desc.strip()),
                        ("code", code),
                        ("amount", amt),
                    ]))

    except Exception:
        pass

    # fallback 1: "CODE  DESC  $AMT"
    if not items:
        for m in re.finditer(
            r"^(?!\s*(?:Sub\s*Total|Subtotal|Discount|Total|Tax(?:\s*Rate)?)\b)"
            r"([A-Z]{1,4}-?\d{2,4})\s+(.+?)\s+\$?([\d,]+\.\d{2})$",
            prepped_text,
            flags=re.MULTILINE
        ):
            code, desc, amt = m.groups()
            items.append(OrderedDict([
                ("description", desc.strip()),
                ("code", code),
                ("amount", clean_and_convert("amount", amt)),
            ]))

    # fallback 2: "DESC  CODE  $AMT"
    if not items:
        for m in re.finditer(
            r"^(?!\s*(?:Sub\s*Total|Subtotal|Discount|Total|Tax(?:\s*Rate)?)\b)"
            r"(.+?)\s+([A-Z]{1,4}-?\d{2,4})\s+\$?([\d,]+\.\d{2})$",
            prepped_text,
            flags=re.MULTILINE
        ):
            desc, code, amt = m.groups()
            # skip header-like junk
            if re.search(r"\bdescription\b.*\bcode\b", desc, flags=re.I):
                continue

            items.append(OrderedDict([
                ("description", desc.strip()),
                ("code", code),
                ("amount", clean_and_convert("amount", amt)),
            ]))

    # fallback 3: "DESC  $AMT" (code maybe embedded in desc)
    if not items:
        for m in re.finditer(
            r"^(?!\s*(?:Sub\s*Total|Subtotal|Discount|Total|Tax(?:\s*Rate)?)\b)"
            r"(.+?)\s+\$?([\d,]+\.\d{2})$",
            prepped_text,
            flags=re.MULTILINE
        ):
            desc, amt = m.groups()

            # ignore summary rows
            if _is_summary_row(desc, ""):
                continue

            # try to pull code from inside desc
            cand_code = None
            mcode = re.search(r"([A-Z]{1,4}-?\d{2,4})", desc)
            if mcode:
                cand_code = mcode.group(1)
                desc = re.sub(
                    r"\b" + re.escape(cand_code) + r"\b",
                    "",
                    desc
                ).strip()

            items.append(OrderedDict([
                ("description", desc.strip()),
                ("code", cand_code),
                ("amount", clean_and_convert("amount", amt)),
            ]))

    return items

# ---------------- Parse orchestration ----------------
def parse_invoice(
    prepped_text: str,
    page,
    admission_override=None,
    discharge_override=None
) -> dict:
    data = extract_fields(prepped_text)

    # lock in admission_date / discharge_date from raw if we captured them
    if (not data.get("admission_date")) and admission_override:
        data["admission_date"] = norm_date(admission_override)

    if (not data.get("discharge_date")) and discharge_override:
        data["discharge_date"] = norm_date(discharge_override)

    # geometry-based address override for T1 only
    template = detect_template(prepped_text) if 'detect_template' in globals() else None
    if template == "T1":  # Hot Springs General Hospital
        addr_geo = extract_address_T1_spatial(page)
        if addr_geo:
            data["patient_address"] = addr_geo

    # T3 "BILLED TO" fallback for name/address
    if not data.get("patient_name") or not data.get("patient_address"):
        bt_name, bt_addr = _extract_billed_to(prepped_text)
        if bt_name and not data.get("patient_name"):
            data["patient_name"] = bt_name
        if bt_addr and not data.get("patient_address"):
            data["patient_address"] = bt_addr

    # If still missing name, try generic fallback
    if not data.get("patient_name"):
        pn = _patient_name_fallback(prepped_text)
        if pn:
            data["patient_name"] = pn

    # clean trailing junk from address and normalize again
    if data.get("patient_address"):
        addr = data["patient_address"]
        addr = re.sub(r"[.\u2024\u2027\u2219\u22C5\u00B7]{2,}", " ", addr)
        addr = re.sub(
            r"\b(Admission\s*Date|Discharge\s*Date|Patient\s*Age|Hospital\s*No|Bed\s*No|Consultant|Phone|Email)\b.*$",
            "",
            addr,
            flags=re.IGNORECASE
        )
        addr = re.sub(r"\s*\n\s*", ", ", addr)
        addr = re.sub(r"\s{2,}", " ", addr).strip(" ,;:-")
        if addr.lower().startswith("admission") or len(addr) < 8:
            addr = None
        data["patient_address"] = _normalize_us_address(addr) if addr else None

    # if still no due_date, guess from header near invoice_date
    if not data.get("due_date"):
        lines = prepped_text.splitlines()
        header = []
        for line in lines:
            header.append(line)
            if re.search(r"\bPatient\s+Details\b", line, re.IGNORECASE):
                break
        hdr = "\n".join(header)

        raw_dates = re.findall(DATE_TOKEN, hdr)
        canon = [d for d in (norm_date(x) for x in raw_dates) if d]

        inv = data.get("invoice_date")
        if inv and inv in canon and len(canon) > 1:
            # first non-invoice-date date after invoice date
            data["due_date"] = next((d for d in canon if d != inv), None)
        elif len(canon) >= 2:
            data["due_date"] = canon[1]

        # net terms fallback
        if not data.get("due_date") and inv:
            m_net = re.search(r"Net\s+(\d{1,3})", hdr, re.IGNORECASE)
            if m_net:
                try:
                    y, mth, d = map(int, inv.split("-"))
                    invd = date(y, mth, d)
                    data["due_date"] = (
                        invd + timedelta(days=int(m_net.group(1)))
                    ).isoformat()
                except Exception:
                    pass

    data["line_items"] = extract_line_items(page, prepped_text)

    # purge lingering tax keys
    for k in list(data.keys()):
        if k.lower().startswith("tax"):
            data.pop(k, None)

    # final uniform formatting (phones, spacing, address, etc.)
    data = _postprocess_uniformity(data)
    return data

# ---------------- PDF entrypoint ----------------
def parse_pdf_bytes(pdf_bytes: bytes) -> dict:
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[0]
            raw_text = page.extract_text()
            if not raw_text:
                return {"error": "Could not extract text from PDF."}

            # detect which template this PDF is
            templ = detect_template(raw_text)

            # run template-specific preprocessing
            if templ == "T1":
                prepped_text, adm_raw, dis_raw = _preprocess_T1(raw_text)
            elif templ == "T2":
                prepped_text, adm_raw, dis_raw = _preprocess_T2(raw_text)
            elif templ == "T3":
                prepped_text, adm_raw, dis_raw = _preprocess_T3(raw_text)
            else:
                # fallback: treat like T1-lite but with no admission/discharge lock
                prepped_text, adm_raw, dis_raw = _preprocess_T1(raw_text)

            parsed = parse_invoice(
                prepped_text,
                page,
                admission_override=adm_raw,
                discharge_override=dis_raw
            )

            return normalize_to_invoice_schema_v1(parsed)

    except Exception as e:
        return {"error": f"An unexpected error occurred during PDF processing: {e}"}
