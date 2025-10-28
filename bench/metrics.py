import pandas as pd

def exact_match(pred, truth):
    return 1 if (pred is not None and str(pred).strip() == str(truth).strip()) else 0

def numeric_delta_ok(pred, truth, tol=0.01):
    try:
        return 1 if pred is not None and abs(float(pred) - float(truth)) <= tol else 0
    except Exception:
        return 0

def cell_match_rate(pred_df: pd.DataFrame, gt_df: pd.DataFrame):
    if pred_df is None or gt_df is None:
        return None
    r = min(pred_df.shape[0], gt_df.shape[0])
    c = min(pred_df.shape[1], gt_df.shape[1])
    if r == 0 or c == 0:
        return 0.0
    pred = pred_df.iloc[:r, :c].astype(str).applymap(str.strip)
    gt = gt_df.iloc[:r, :c].astype(str).applymap(str.strip)
    correct = (pred.values == gt.values).sum()
    return correct / (r * c)
