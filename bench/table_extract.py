# table_extract.py
from typing import Dict, List, Any
import pandas as pd

def camelot_extract(pdf_path) -> Dict[str, List[pd.DataFrame]]:
    """
    Returns a dict of variant -> list[DataFrame].
    Variants: 'camelot_lattice', 'camelot_stream'
    """
    import camelot  # requires ghostscript & opencv
    out = {}

    try:
        tables_lat = camelot.read_pdf(str(pdf_path), flavor="lattice", pages="1-end")
        out["camelot_lattice"] = [t.df for t in tables_lat] if tables_lat else []
    except Exception:
        out["camelot_lattice"] = []

    try:
        tables_str = camelot.read_pdf(str(pdf_path), flavor="stream", pages="1-end")
        out["camelot_stream"] = [t.df for t in tables_str] if tables_str else []
    except Exception:
        out["camelot_stream"] = []

    return out

def tabula_extract(pdf_path) -> Dict[str, List[pd.DataFrame]]:
    """
    Returns a dict of variant -> list[DataFrame].
    Variant: 'tabula'
    """
    try:
        import tabula  # requires Java
        dfs = tabula.read_pdf(str(pdf_path), pages="all", multiple_tables=True)
        return {"tabula": dfs or []}
    except Exception:
        return {"tabula": []}

def pick_first_table(dfs: List[pd.DataFrame]):
    return dfs[0] if dfs else None

def load_ground_truth_lineitems(gt_dir, pdf_filename) -> pd.DataFrame:
    """
    Load ground-truth line-items CSV for a given PDF (same stem).
    """
    import os
    from pathlib import Path
    stem = Path(pdf_filename).stem
    csv_path = Path(gt_dir) / f"{stem}_lineitems.csv"
    if not csv_path.exists():
        return pd.DataFrame()  # empty -> no GT
    return pd.read_csv(csv_path)
