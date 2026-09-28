import glob
import os
import re
import sys

import numpy as np
import pandas as pd

ORDER = ["mAGA", "mLSL", "mASG"]

FIJI_COLMAP = {
    "Area": "area_um2", "AR": "aspect_ratio", "EquivDiam": "equiv_diam_um",
    "Condition": "condition", "SourceFile": "file", "ObjectID": "label",
}
OUT_COLS = ["condition", "file", "label", "equiv_diam_um", "aspect_ratio"]

def condition_from_name(fname):
    stem = re.sub(r"_manual$", "", os.path.splitext(os.path.basename(fname))[0])
    for key in ORDER:
        if key in stem:
            return key
    parts = stem.split("_")
    return parts[1] if len(parts) > 1 else stem

def load_manual(indir):
    files = sorted(glob.glob(os.path.join(indir, "*_manual.csv")))
    if not files:
        raise SystemExit(f"no *_manual.csv in {indir}")
    frames = []
    for path in files:
        df = pd.read_csv(path).rename(columns=FIJI_COLMAP)
        if "condition" not in df:
            df["condition"] = condition_from_name(path)
        if "file" not in df:
            df["file"] = os.path.basename(path)
        if "label" not in df:
            df["label"] = np.arange(1, len(df) + 1)
        if "equiv_diam_um" not in df:
            df["equiv_diam_um"] = 2 * np.sqrt(df["area_um2"] / np.pi)
        frames.append(df[[c for c in OUT_COLS if c in df.columns]])
    return pd.concat(frames, ignore_index=True)

def wide(df, col):
    conds = [c for c in ORDER if c in set(df.condition)]
    conds += [c for c in df.condition.unique() if c not in conds]
    return pd.concat({c: df.loc[df.condition == c, col].reset_index(drop=True)
                      for c in conds}, axis=1)

def main():
    if len(sys.argv) > 1:
        indir = sys.argv[1]
    else:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        indir = filedialog.askdirectory(title="Folder with the *_manual.csv files")
        root.destroy()
    if not indir:
        raise SystemExit("cancelled")

    df = load_manual(indir)

    outdir = os.path.join(indir, "shape_out")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "condensate_shape.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="objects", index=False)
        wide(df, "equiv_diam_um").to_excel(w, sheet_name="equiv_diam_um", index=False)
        wide(df, "aspect_ratio").to_excel(w, sheet_name="aspect_ratio", index=False)

    print(df.groupby("condition").size().rename("n condensates").to_string())
    print(f"written to {path}")

if __name__ == "__main__":
    main()
