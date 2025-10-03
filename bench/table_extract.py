from pathlib import Path
import pandas as pd
import camelot
import tabula

def camelot_extract(pdf_path: Path):
    out = {}
    try:
        out["camelot_lattice"] = [t.df for t in camelot.read_pdf(str(pdf_path), pages="all", flavor="lattice")]
    except Exception:
        out["camelot_lattice"] = []
    try:
        out["camelot_stream"] = [t.df for t in camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")]
    except Exception:
        out["camelot_stream"] = []
    return out

def tabula_extract(pdf_path: Path):
    try:
        dfs = tabula.read_pdf(str(pdf_path), pages="all", multiple_tables=True)
        return {"tabula": dfs or []}
    except Exception:
        return {"tabula": []}

def pick_first_table(dfs_list):
    if not dfs_list:
        return None
    picks = [(df.shape[0]*df.shape[1], df) for df in dfs_list]
    picks.sort(key=lambda x: x[0], reverse=True)
    return picks[0][1]

def load_ground_truth_lineitems(gt_dir: Path, filename: str):
    p = gt_dir / f"{Path(filename).name}.csv"
    return pd.read_csv(p) if p.exists() else None
