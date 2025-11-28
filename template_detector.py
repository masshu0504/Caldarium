# template_detector.py
# --------------------
# Shared module for template layout fingerprinting and unforeseen template detection.

from __future__ import annotations

import os
import json
import math
from datetime import datetime
from collections import Counter
from typing import Dict, Tuple, Optional

import pdfplumber


# -----------------------------
# CONFIG / CONSTANTS
# -----------------------------

# Where known template fingerprints are stored.
# This should be a JSON file mapping template_id -> fingerprint dict.
KNOWN_FP_PATH = "known_template_fingerprints.json"

# Where to log detection events (JSONL).
TEMPLATE_DETECTION_LOG = "template_detection_report.jsonl"

# Keywords to help distinguish templates (can tweak over time)
KEYWORD_GROUPS = {
    "kw_hot_springs": [
        "HOT SPRINGS GENERAL HOSPITAL",
        "HOT SPRINGS GENERAL",
    ],
    "kw_rose_petal": [
        "ROSE PETAL CLINIC",
        "ROSE PETAL",
    ],
    "kw_white_petal": [
        "WHITE PETAL HOSPITAL",
        "WHITE PETAL",
    ],
    # generic
    "kw_clinic": ["clinic"],
    "kw_hospital": ["hospital"],

    # 👇 NEW: consent-related keywords
    "kw_consent": [
        "consent",
        "consent form",
        "informed consent",
    ],
    "kw_hipaa": [
        "hipaa authorization",
        "hipaa",
    ],
    "kw_authorization": [
        "authorization form",
        "authorization",
        "authorize",
        "authorizes",
    ],
}


# -----------------------------
# FINGERPRINTING
# -----------------------------

def detect_template_signature(pdf_path: str) -> Dict:
    """
    Compute a simple layout fingerprint for a PDF.

    Features include:
      - page_count
      - avg_width, avg_height
      - header/body/footer text density (by char count)
      - avg_font_size
      - top_fonts (up to 3 most common font names)

    This is intentionally lightweight and stable across runs.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")


    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        widths = []
        heights = []
        all_font_sizes = []
        all_fonts = []

        header_chars = 0
        body_chars = 0
        footer_chars = 0
        total_chars = 0

        all_text_chunks = []  # 👈 NEW

        for page in pdf.pages:
            widths.append(page.width)
            heights.append(page.height)

            h = float(page.height)
            header_y = h * 0.8
            footer_y = h * 0.2

            chars = getattr(page, "chars", []) or []
            for ch in chars:
                try:
                    y = float(ch.get("y0", 0.0))
                except (TypeError, ValueError):
                    y = 0.0

                size = ch.get("size")
                try:
                    size = float(size) if size is not None else 0.0
                except (TypeError, ValueError):
                    size = 0.0

                fontname = ch.get("fontname", "unknown")

                total_chars += 1
                all_font_sizes.append(size)
                all_fonts.append(fontname)

                if y >= header_y:
                    header_chars += 1
                elif y <= footer_y:
                    footer_chars += 1
                else:
                    body_chars += 1

            # 👇 Grab text for keyword analysis
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            if page_text:
                all_text_chunks.append(page_text)

        def avg(lst):
            return float(sum(lst) / len(lst)) if lst else 0.0

        font_counter = Counter(all_fonts)
        top_fonts = [f for f, _ in font_counter.most_common(3)]

        full_text = "\n".join(all_text_chunks).lower()

        # 👇 Keyword-based features (counts)
        keyword_features = {}
        for feat_name, phrases in KEYWORD_GROUPS.items():
            count = 0
            for p in phrases:
                count += full_text.count(p.lower())
            keyword_features[feat_name] = float(count)  # numeric for vector


        fingerprint = {
            "page_count": page_count,
            "avg_width": avg(widths),
            "avg_height": avg(heights),
            "header_text_density": header_chars / total_chars if total_chars else 0.0,
            "footer_text_density": footer_chars / total_chars if total_chars else 0.0,
            "body_text_density": body_chars / total_chars if total_chars else 0.0,
            "avg_font_size": avg(all_font_sizes),
            "top_fonts": top_fonts,
        }

        # merge keyword features
        fingerprint.update(keyword_features)

    return fingerprint



# -----------------------------
# KNOWN FINGERPRINTS
# -----------------------------

def load_known_fingerprints(path: str = KNOWN_FP_PATH) -> Dict[str, Dict]:
    """
    Load known template fingerprints from a JSON file.

    Expected structure:
      {
        "T1_hot_springs": { ... fingerprint dict ... },
        "T2_rose_petal": { ... },
        ...
      }
    """
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data or {}


# -----------------------------
# SIMILARITY
# -----------------------------

def _fp_to_vector(fp: Dict) -> list[float]:
    """
    Convert a fingerprint dict to a numeric vector for similarity comparison.
    Keep this in sync with detect_template_signature.
    """
    base_vector = [
        float(fp.get("page_count", 0)),
        float(fp.get("avg_width", 0.0)),
        float(fp.get("avg_height", 0.0)),
        float(fp.get("header_text_density", 0.0)),
        float(fp.get("footer_text_density", 0.0)),
        float(fp.get("body_text_density", 0.0)),
        float(fp.get("avg_font_size", 0.0)),
    ]

    # 👇 Add keyword-based dimensions (must be deterministic order)
    keyword_vector = [
        float(fp.get("kw_hot_springs", 0.0)),
        float(fp.get("kw_rose_petal", 0.0)),
        float(fp.get("kw_white_petal", 0.0)),
        float(fp.get("kw_clinic", 0.0)),
        float(fp.get("kw_hospital", 0.0)),
        float(fp.get("kw_consent", 0.0)),       # NEW
        float(fp.get("kw_hipaa", 0.0)),         # NEW
        float(fp.get("kw_authorization", 0.0)), # NEW
    ]

    return base_vector + keyword_vector


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def fingerprint_similarity(fp1: Dict, fp2: Dict) -> float:
    """
    Compute a similarity score between two fingerprints in [0, 1].

    Uses cosine similarity over the numeric fields, plus:
      - small bonus if primary font matches
      - 50% penalty if the doc has none of the known hospital names/titles
      - +0.50 bonus if the doc has consent-related keywords
    """
    v1 = _fp_to_vector(fp1)
    v2 = _fp_to_vector(fp2)
    base_sim = _cosine_similarity(v1, v2)

    # Small bump if the primary font matches.
    fonts1 = fp1.get("top_fonts", [])
    fonts2 = fp2.get("top_fonts", [])
    font_bonus = 0.0
    if fonts1 and fonts2 and fonts1[0] == fonts2[0]:
        font_bonus = 0.05

    score = base_sim + font_bonus
    score = max(0.0, min(1.0, score))  # initial clamp

    # 1) 50% PENALTY if no hospital name / title keywords
    NAME_KEYS = ("kw_hot_springs", "kw_rose_petal", "kw_white_petal")
    has_any_name = any(fp1.get(k, 0.0) > 0.0 for k in NAME_KEYS)
    if not has_any_name:
        score *= 0.5  # bring it down by 50%

    # 2) +0.50 BONUS if this document looks like a consent form
    CONSENT_KEYS = ("kw_consent", "kw_hipaa", "kw_authorization")
    has_consent_keywords = any(fp1.get(k, 0.0) > 0.0 for k in CONSENT_KEYS)
    if has_consent_keywords:
        score += 0.5  # add 50 percentage points

    # Final clamp to [0, 1]
    score = max(0.0, min(1.0, score))
    return score



# -----------------------------
# CLASSIFICATION
# -----------------------------

def classify_template(
    signature: Dict,
    threshold: float = 0.85,
    known_fingerprints: Optional[Dict[str, Dict]] = None,
) -> Tuple[str, float, bool]:
    """
    Given a layout fingerprint, find the most similar known template.

    Returns:
      (best_template_id, similarity_score, is_unforeseen)

    - best_template_id: template key from known_fingerprints, or "unknown"
    - similarity_score: float in [0, 1]
    - is_unforeseen: True if similarity_score < threshold
    """
    known = known_fingerprints if known_fingerprints is not None else load_known_fingerprints()

    if not known:
        # No reference fingerprints yet – treat everything as unforeseen.
        return "unknown", 0.0, True

    best_id = None
    best_score = -1.0

    for template_id, fp in known.items():
        try:
            score = fingerprint_similarity(signature, fp)
        except Exception:
            # If anything is broken with this fp, skip it.
            continue

        if score > best_score:
            best_score = score
            best_id = template_id

    if best_id is None:
        return "unknown", 0.0, True

    is_unforeseen = best_score < threshold
    return best_id, best_score, is_unforeseen


def check_for_unforeseen_template(
    pdf_path: str,
    run_id: str,
    doc_id: str,
) -> str:
    """
    High-level helper used by consent_parser (and others).

    1. Builds a layout+keyword fingerprint from the PDF.
    2. Classifies it against known fingerprints.json.
    3. Logs the detection event.
    4. Returns:
        - "unforeseen"  if below the similarity threshold
        - template_id   otherwise (e.g., "nih_consent", "hipaa_consent", "T1_hot_springs")
    """
    # 1) Build fingerprint for this PDF
    signature = detect_template_signature(pdf_path)

    # 2) Classify against known fingerprints
    template_id, score, is_unforeseen = classify_template(signature)

    # 3) Log detection event
    log_template_detection(
        run_id=run_id,
        doc_id=doc_id,
        template_id=template_id,
        score=score,
        is_unforeseen=is_unforeseen,
        meta={"source": "consent_parser"}  # or "invoice_parser", etc. if you reuse
    )

    # 4) Interpret result for the caller
    if is_unforeseen:
        return "unforeseen"

    # For consents, just make sure your known_template_fingerprints.json
    # uses keys like "nih_consent" and "hipaa_consent" for those layouts.
    return template_id


# -----------------------------
# LOGGING
# -----------------------------

def log_template_detection(
    run_id: str,
    doc_id: str,
    template_id: str,
    score: float,
    is_unforeseen: bool,
    path: str = TEMPLATE_DETECTION_LOG,
    meta: Optional[Dict] = None,
) -> None:
    """
    Append a single detection event to template_detection_report.jsonl.

    Each line is a JSON object like:
      {
        "timestamp": "...Z",
        "run_id": "...",
        "doc_id": "...",
        "detected_template": "T1_hot_springs",
        "similarity_score": 0.92,
        "is_unforeseen": false,
        "meta": { ... }   # optional
      }
    """
    record = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run_id": run_id,
        "doc_id": doc_id,
        "detected_template": template_id,
        "similarity_score": float(score),
        "is_unforeseen": bool(is_unforeseen),
    }
    if meta:
        record["meta"] = meta

    # Make sure parent folder exists if path has one
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
