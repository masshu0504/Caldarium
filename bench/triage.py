from pathlib import Path
from pdfminer.high_level import extract_text
import pandas as pd

def has_embedded_text(pdf_path: Path, min_chars: int = 30) -> bool:
    try:
        txt = extract_text(str(pdf_path)) or ""
        return len(txt.strip()) >= min_chars
    except Exception:
        return False

def triage_folder(pdf_dir: Path, out_csv: Path) -> pd.DataFrame:
    """
    Triage PDFs by presence of embedded text.

    - DIGITAL       -> embedded text present (>= min_chars)
    - SCANNED_PDF   -> no embedded text (likely scanned/image-only or corrupted)
    """
    rows = []
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        embedded = has_embedded_text(pdf)
        status = "DIGITAL" if embedded else "SCANNED_PDF"
        taxonomy_tag = "doc.type=digital" if embedded else "doc.type=scanned"
        rows.append({
            "filename": pdf.name,
            "embedded_text": embedded,
            "triage_status": status,
            "taxonomy_tag": taxonomy_tag,
        })
    df = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    return df
