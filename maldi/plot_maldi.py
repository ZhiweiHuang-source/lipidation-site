import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WINDOW_DA = 6200.0
TITLE_FONTSIZE = 22
LABEL_FONTSIZE = 18
TICK_FONTSIZE = 14


def norm_name(s):
    s = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", str(s)).strip().replace(" ", "")
    s = re.sub(r"\(([^)]*)\)", lambda m: "(" + m.group(1).replace("_", "/") + ")", s)
    return s.lower()


def display_name(s):
    s = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", str(s)).strip()
    s = re.sub(r"\(([^)]*)\)", lambda m: "(" + m.group(1).replace("_", "/") + ")", s)
    return s


def title_text(s):
    s = re.sub(r"(?i)\b(?:15N|N15)\b", r"$^{15}$N", display_name(s))
    return re.sub(r"(?<=[A-Za-z\)])(\d+)(?!\d)", r"$_{\1}$", s)


def safe_stem(s):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", display_name(s))
    return re.sub(r"_+", "_", s).strip("._ ") or "spectrum"


def read_spectra(path):
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    cols = list(df.columns)
    pairs = []
    if any(c.startswith("m_z_") for c in cols):
        lower = {c.lower(): c for c in cols}
        for i, c in enumerate(cols):
            if not c.startswith("m_z_"):
                continue
            name = c.split("m_z_", 1)[1].strip()
            ic = lower.get(f"intensity_{name.lower()}")
            if ic is None and i + 1 < len(cols) and cols[i + 1].lower().startswith("intensity"):
                ic = cols[i + 1]
            if ic is not None:
                pairs.append((name, c, ic))
    else:
        for i in range(1, len(cols), 2):
            pairs.append((cols[i], cols[i - 1], cols[i]))
    spectra = {}
    for name, mc, ic in pairs:
        mz = pd.to_numeric(df[mc], errors="coerce")
        inten = pd.to_numeric(df[ic], errors="coerce")
        ok = mz.notna() & inten.notna()
        if ok.any():
            spectra[name] = (mz[ok].to_numpy(float), inten[ok].to_numpy(float))
    return spectra


def read_theoretical(path):
    df = pd.read_csv(path)
    names, values = df.columns[0], df.columns[1]
    out = {}
    for n, v in zip(df[names], df[values]):
        v = pd.to_numeric(str(v).replace(",", ""), errors="coerce")
        if pd.notna(v):
            out[norm_name(n)] = float(v)
    return out


def analyse(name, mz, inten, theo, outdir):
    center = theo if theo is not None else (mz.min() + mz.max()) / 2.0
    x0, x1 = center - WINDOW_DA / 2.0, center + WINDOW_DA / 2.0
    win = (mz >= x0) & (mz <= x1)
    if not win.any():
        win = np.ones_like(mz, dtype=bool)
    mz_w, int_w = mz[win], inten[win]
    obs = float(mz_w[np.argmax(int_w)])

    fig, ax = plt.subplots(figsize=(6.0, 5.0), dpi=220)
    ax.plot(mz_w, int_w, color="#FF8C00", linewidth=1.2)
    if theo is not None:
        ax.axvline(theo, color="#1f77b4", linestyle="--", linewidth=1.2)
    ax.set_title(title_text(name), fontsize=TITLE_FONTSIZE)
    ax.set_xlabel("m/z", fontsize=LABEL_FONTSIZE)
    ax.set_ylabel("Intensity", fontsize=LABEL_FONTSIZE)
    ax.tick_params(axis="both", labelsize=TICK_FONTSIZE)
    ax.set_xlim(x0, x1)
    fig.tight_layout()
    fig.savefig(outdir / f"{safe_stem(name)}.png", bbox_inches="tight")
    plt.close(fig)
    return obs


def pick_files():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    theo = filedialog.askopenfilename(title="Theoretical masses (CSV: construct, m/z)")
    spectra = filedialog.askopenfilenames(title="MALDI spectra (one or more CSV files)")
    root.destroy()
    return theo, list(spectra)


def main():
    args = sys.argv[1:]
    if "--window" in args:
        i = args.index("--window")
        global WINDOW_DA
        WINDOW_DA = float(args[i + 1])
        del args[i:i + 2]
    theo_path, spectra_paths = (args[0], args[1:]) if len(args) >= 2 else pick_files()
    if not theo_path or not spectra_paths:
        raise SystemExit("cancelled")

    theoretical = read_theoretical(theo_path)
    outdir = Path(spectra_paths[0]).parent / "maldi_output"
    outdir.mkdir(exist_ok=True)

    rows, seen = [], {}
    for p in spectra_paths:
        for name, (mz, inten) in read_spectra(p).items():
            key = norm_name(name)
            if key in seen:
                raise SystemExit(f"'{name}' appears in both {seen[key]} and {Path(p).name}; "
                                 "rename one of them.")
            seen[key] = Path(p).name
            theo = theoretical.get(key)
            obs = analyse(name, mz, inten, theo, outdir)
            err = (obs - theo) / theo * 100 if theo else None
            rows.append((display_name(name), obs, theo, err))

    table = pd.DataFrame(rows, columns=["Construct", "m/z observed",
                                        "m/z theoretical", "Error (%)"])
    table = table.sort_values("Construct", key=lambda s: s.map(norm_name)).round(3)
    table.to_csv(outdir / "maldi_masses.csv", index=False)
    print(f"{len(table)} spectra -> {outdir.resolve()}")


if __name__ == "__main__":
    main()
