import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SAMPLES = {
    "2": "MG 80%",
    "4": "MG 80% + mAAS", "6": "MG 80% + mAAS_RGD",
    "7": "MG 80% + mLAA",
    "8": "MG 80% + mAAG", "9": "MG 80% + mAAG_RGD",
}
BATCHES = ["0724", "0727", "0729", "0731", "0803", "0807", "0904"]
CONTROL = "MG 80%"

PANELS = {
    "material_state": dict(
        conditions=["MG 80% + mAAS", "MG 80% + mLAA", "MG 80% + mAAG"],
        metrics=["budding_pct", "non_spheroid_pct", "cyst_pct",
                 "organoid_pct", "spheroid_pct"]),
    "RGD": dict(
        conditions=["MG 80% + mAAG", "MG 80% + mAAG_RGD",
                    "MG 80% + mAAS", "MG 80% + mAAS_RGD"],
        metrics=["CFE_pct"]),
}
NORMALISED = {"CFE_pct", "budding_pct"}
TITLES = {"CFE_pct": "CFE, % of control",
          "budding_pct": "Budding organoids, % of control",
          "non_spheroid_pct": "Non-spheroid colonies, %",
          "cyst_pct": "Cysts, %", "organoid_pct": "Organoids, %",
          "spheroid_pct": "Spheroids, %"}

FIX_MANUAL_BY_CLASS = {"0727"}
ORGANOID_CLASSES = ("EarlyOrganoid", "LateOrganoid")

SEED_DENSITY = 5000
EXPECTED_FIELDS = 4
MIN_DIAM_UM = 50.0
DAY4_MIN_DIAM_UM = 70.0
UM_PER_PX = 0.8848
IMAGE_W_PX, IMAGE_H_PX = 4032, 3040
CLASSES = ["Cyst", "EarlyOrganoid", "LateOrganoid", "Spheroid"]
_PCT = EXPECTED_FIELDS / SEED_DENSITY * 100

def _parts(v):
    return [y for y in Path(str(v)).stem.replace("-", "_").split("_") if y]

def sample_of(v):
    p = _parts(v)
    return p[0] if p else "NA"

def gel_of(v):
    return "_".join(_parts(v)[:2])

def apply_floor(d, floor_um):
    diam = np.sqrt((d["w"] * IMAGE_W_PX * UM_PER_PX)
                   * (d["h"] * IMAGE_H_PX * UM_PER_PX))
    return d[diam >= floor_um]

def fields_per_gel(folder, batch, d):
    for c in (folder / f"{batch}_day2_per_gel_fields.csv",
              folder / f"{batch}_per_gel_fields.csv"):
        if c.exists():
            f = pd.read_csv(c)
            return {str(g).replace("-", "_"): float(n)
                    for g, n in zip(f["gel"], f["n_fields_analysed"])
                    if n == n and n > 0}
    idx = d["filename"].apply(lambda v: int(_parts(v)[2]))
    return ((idx - 1) // 2 + 1).groupby(d["_g"]).nunique().to_dict()

def per_gel_day2(folder, batch):
    p = folder / f"{batch}_AllDetections_clean.csv"
    if not p.exists():
        return None
    d = apply_floor(pd.read_csv(p), MIN_DIAM_UM)
    d = d.assign(_s=d["filename"].apply(sample_of), _g=d["filename"].apply(gel_of))
    g = d.groupby(["_s", "_g"]).size().rename("colonies").reset_index()
    g["n_fields"] = g["_g"].map(fields_per_gel(folder, batch, d))
    g["n_fields"] = g["n_fields"].fillna(EXPECTED_FIELDS)
    return g.rename(columns={"_s": "sample", "_g": "gel"})

def per_gel_day4(folder, batch):
    p = folder / f"{batch}_budding_scores.csv"
    if not p.exists():
        return None
    d = apply_floor(pd.read_csv(p), DAY4_MIN_DIAM_UM)
    ccol = "classorg" if "classorg" in d.columns else "class"
    d = d.assign(_s=d["filename"].apply(sample_of), _g=d["filename"].apply(gel_of))
    if batch in FIX_MANUAL_BY_CLASS and "source" in d.columns:
        man = d["source"].astype(str).eq("manual")
        d.loc[man, "score"] = np.where(
            d.loc[man, ccol].isin(ORGANOID_CLASSES), "budding", "not_budding")
    d["_bud"] = d["score"].astype(str).eq("budding")
    g = (d.groupby(["_s", "_g"])
           .agg(n_scored=("_bud", "size"), n_budding=("_bud", "sum"))
           .reset_index())
    cls = (d.groupby(["_s", "_g"])[ccol].value_counts().unstack(fill_value=0)
             .reindex(columns=CLASSES, fill_value=0).reset_index())
    return g.merge(cls, on=["_s", "_g"]).rename(columns={"_s": "sample", "_g": "gel"})

def load(folder):
    rows = []
    for b in BATCHES:
        for day, fn in (("day2", per_gel_day2), ("day4", per_gel_day4)):
            g = fn(folder, b)
            if g is None:
                continue
            g["batch"], g["day"] = b, day
            g["condition"] = g["sample"].map(SAMPLES)
            rows.append(g[g.condition.notna()])
    return pd.concat(rows, ignore_index=True)

def per_batch(per_gel):
    num = [c for c in ["colonies", "n_fields", "n_scored", "n_budding"] + CLASSES
           if c in per_gel.columns]
    pooled = (per_gel.groupby(["batch", "day", "condition"])[num].sum()
                     .assign(n_gels=per_gel.groupby(["batch", "day", "condition"])
                             .gel.nunique())
                     .reset_index())
    d2 = pooled[pooled.day == "day2"].copy()
    d2["CFE_pct"] = d2["colonies"] / d2["n_fields"].replace(0, np.nan) * _PCT
    d2 = d2[["batch", "condition", "n_gels", "colonies", "n_fields", "CFE_pct"]]

    d4 = pooled[pooled.day == "day4"].copy()
    d4["budding_pct"] = d4["n_budding"] / d4["n_scored"].replace(0, np.nan) * 100.0
    d4["Organoid"] = d4[["EarlyOrganoid", "LateOrganoid"]].sum(axis=1)
    tot = d4[["Cyst", "Organoid", "Spheroid"]].sum(axis=1).replace(0, np.nan)
    for k in ("Cyst", "Organoid", "Spheroid"):
        d4[k.lower() + "_pct"] = 100 * d4[k] / tot
    d4["non_spheroid_pct"] = d4["cyst_pct"] + d4["organoid_pct"]
    d4 = d4[["batch", "condition", "n_gels", "n_scored", "n_budding"] + CLASSES
            + ["budding_pct", "cyst_pct", "organoid_pct", "spheroid_pct",
               "non_spheroid_pct"]]
    return d2.merge(d4, on=["batch", "condition"], how="outer",
                    suffixes=("_day2", "_day4"))

def panel_table(tab, metric, control, conditions, normalise):
    piv = tab.pivot_table(index="condition", columns="batch", values=metric)
    piv = piv.reindex(list(dict.fromkeys(conditions + [control])))
    complete = piv.notna().all(axis=0)
    if normalise:
        piv = piv.divide(piv.loc[control], axis=1) * 100.0
    return piv.loc[conditions, complete].T

def main():
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
    else:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        folder = Path(filedialog.askdirectory(title="Folder with the batch CSVs"))
        root.destroy()
    if not folder.is_dir():
        raise SystemExit("no folder")
    out = folder / "analysis"
    out.mkdir(exist_ok=True)

    tab = per_batch(load(folder))
    with pd.ExcelWriter(out / "organoid_metrics.xlsx", engine="openpyxl") as w:
        tab.round(4).to_excel(w, sheet_name="per_batch", index=False)
        for name, spec in PANELS.items():
            row = 0
            for metric in spec["metrics"]:
                t = panel_table(tab, metric, CONTROL, spec["conditions"],
                                metric in NORMALISED)
                pd.DataFrame([[TITLES[metric]]]).to_excel(
                    w, sheet_name=name, startrow=row, index=False, header=False)
                t.round(4).to_excel(w, sheet_name=name, startrow=row + 1)
                row += len(t) + 4
    print(f"written to {(out / 'organoid_metrics.xlsx').resolve()}")

if __name__ == "__main__":
    main()
