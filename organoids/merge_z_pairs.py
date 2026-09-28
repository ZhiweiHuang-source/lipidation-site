import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

IMAGES_PER_FIELD = 2

SHIFT_TOL = 0.008
MIN_SHIFT_VOTES = 5
MAX_SHIFT = 0.15

IOU_THRESH = 0.45
CONTAINMENT_THRESH = 0.75
CENTER_TOL_FRAC = 0.40

FILENAME_REGEX = r"(?P<gel>[A-Za-z0-9]+[-_]\d+)[-_](?P<idx>\d+)$"

CLASS_MAP = {0: "Cyst", 1: "EarlyOrganoid", 2: "LateOrganoid", 3: "Spheroid"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp",
              ".JPG", ".JPEG", ".PNG", ".TIF", ".TIFF")
OUT_DIR = "z_merged"

def parse_name(stem):
    m = re.search(FILENAME_REGEX, stem)
    if not m:
        return None, None
    return m.group("gel").replace("-", "_"), int(m.group("idx"))

def field_of(idx):
    return (idx - 1) // IMAGES_PER_FIELD + 1

def load_labels(labels_dir, images_dir):
    rows, stems = [], []
    for f in sorted(Path(labels_dir).glob("*.txt")):
        gel, idx = parse_name(f.stem)
        if gel is None:
            continue
        stems.append((f.stem, gel, idx))
        for line in f.read_text().splitlines():
            p = line.split()
            if len(p) < 5:
                continue
            rows.append({
                "image": f.stem, "gel": gel, "idx": idx,
                "classorg": CLASS_MAP.get(int(float(p[0])), p[0]),
                "xc": float(p[1]), "yc": float(p[2]),
                "w": float(p[3]), "h": float(p[4]),
                "confidence": float(p[5]) if len(p) > 5 else 1.0,
            })
    labelled = {s for s, _, _ in stems}

    seen = set()
    for e in IMAGE_EXTS:
        for p in Path(images_dir).glob(f"*{e}"):
            if p.stem in seen:
                continue
            seen.add(p.stem)
            if p.stem in labelled:
                continue
            gel, idx = parse_name(p.stem)
            if gel is not None:
                stems.append((p.stem, gel, idx))

    return (pd.DataFrame(rows),
            pd.DataFrame(stems, columns=["image", "gel", "idx"])
              .drop_duplicates("image").reset_index(drop=True))

def boxes_match(r, k):
    rx, ry = r._xa, r._ya
    kx, ky = k._xa, k._ya
    rx1, rx2 = rx - r.w / 2, rx + r.w / 2
    ry1, ry2 = ry - r.h / 2, ry + r.h / 2
    kx1, kx2 = kx - k.w / 2, kx + k.w / 2
    ky1, ky2 = ky - k.h / 2, ky + k.h / 2
    r_area, k_area = r.w * r.h, k.w * k.h
    iw = max(0.0, min(rx2, kx2) - max(rx1, kx1))
    ih = max(0.0, min(ry2, ky2) - max(ry1, ky1))
    inter = iw * ih
    union = r_area + k_area - inter
    iou = inter / union if union > 0 else 0.0
    contain = inter / min(r_area, k_area) if min(r_area, k_area) > 0 else 0.0
    dist = np.hypot(rx - kx, ry - ky)
    scale = min(min(r.w, r.h), min(k.w, k.h))
    near = dist < CENTER_TOL_FRAC * scale if scale > 0 else False
    return iou >= IOU_THRESH or contain >= CONTAINMENT_THRESH or near

def estimate_shift(a, b):
    if len(a) == 0 or len(b) == 0:
        return 0.0, 0.0, 0
    A = a[["xc", "yc"]].to_numpy(float)
    B = b[["xc", "yc"]].to_numpy(float)
    d = (A[:, None, :] - B[None, :, :]).reshape(-1, 2)
    d = d[(np.abs(d[:, 0]) <= MAX_SHIFT) & (np.abs(d[:, 1]) <= MAX_SHIFT)]
    if len(d) == 0:
        return 0.0, 0.0, 0
    bins = np.arange(-MAX_SHIFT, MAX_SHIFT + SHIFT_TOL, SHIFT_TOL)
    H, xe, ye = np.histogram2d(d[:, 0], d[:, 1], bins=[bins, bins])
    i, j = np.unravel_index(np.argmax(H), H.shape)
    cx, cy = (xe[i] + xe[i + 1]) / 2, (ye[j] + ye[j + 1]) / 2
    near = d[(np.abs(d[:, 0] - cx) <= SHIFT_TOL) &
             (np.abs(d[:, 1] - cy) <= SHIFT_TOL)]
    if len(near) < MIN_SHIFT_VOTES:
        return 0.0, 0.0, int(len(near))
    return float(near[:, 0].mean()), float(near[:, 1].mean()), int(len(near))

def align_planes(grp):
    grp = grp.copy()
    grp["_xa"], grp["_ya"] = grp["xc"], grp["yc"]
    counts = grp.groupby("image").size()
    if len(counts) < 2:
        return grp
    anchor = counts.idxmax()
    a = grp[grp.image == anchor]
    for img in counts.index:
        if img == anchor:
            continue
        dx, dy, votes = estimate_shift(a, grp[grp.image == img])
        if votes:
            m = grp.image == img
            grp.loc[m, "_xa"] = grp.loc[m, "xc"] + dx
            grp.loc[m, "_ya"] = grp.loc[m, "yc"] + dy
    return grp

def dedupe(grp):
    grp = align_planes(grp).sort_values("confidence", ascending=False)
    keep = []
    for _, r in grp.iterrows():
        if not any(k.image != r.image and boxes_match(r, k) for k in keep):
            keep.append(r)
    return pd.DataFrame(keep)

def pick_dir(title):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        p = filedialog.askdirectory(title=title)
        root.destroy()
        return p
    except Exception:
        return input(f"{title}: ").strip().strip('"')

def main():
    labels_dir = sys.argv[1] if len(sys.argv) > 1 else pick_dir(
        "Select the TellU 'labels' folder")
    images_dir = sys.argv[2] if len(sys.argv) > 2 else pick_dir(
        "Select the folder of images TellU was run on")
    if not labels_dir or not images_dir:
        raise SystemExit("cancelled")
    labels_dir, images_dir = Path(labels_dir), Path(images_dir)
    out = labels_dir.parent / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    df, imgs = load_labels(labels_dir, images_dir)
    if df.empty:
        raise SystemExit("no detections found")
    imgs["field"] = [field_of(i) for i in imgs.idx]
    df = df.merge(imgs[["image", "field"]], on="image", how="left")

    kept = pd.concat([dedupe(g) for _, g in df.groupby(["gel", "field"])],
                     ignore_index=True)

    kept["area"] = kept["w"] * kept["h"]
    kept["filename"] = kept["image"] + ".txt"
    kept["sample"] = kept["gel"].astype(str).str.split("_").str[0]
    kept["replicate"] = kept["gel"].astype(str).str.split("_").str[-1]
    kept["image_index"] = kept["idx"]
    kept["field_group"] = kept["gel"].astype(str) + "_f" + kept["field"].astype(str)
    cols = ["classorg", "confidence", "area", "filename", "gel", "sample",
            "replicate", "image_index", "field", "field_group",
            "xc", "yc", "w", "h"]
    kept.sort_values(["gel", "field", "classorg"])[cols] \
        .to_csv(out / "AllDetections_clean.csv", index=False)

    fields = imgs.groupby("gel").agg(n_images=("idx", "nunique"),
                                     n_fields_analysed=("field", "nunique"))
    fields.reset_index().to_csv(out / "per_gel_fields.csv", index=False)

    print(f"{len(df)} detections -> {len(kept)} unique structures "
          f"in {imgs.gel.nunique()} gels")
    print(f"written to {out.resolve()}")

if __name__ == "__main__":
    main()
