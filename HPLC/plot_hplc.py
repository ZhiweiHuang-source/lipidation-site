import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

X_START, X_END = 20.0, 40.0
BASELINE_PERCENTILE = 1.0
SMOOTH_WINDOW = 5
PEAK_THRESHOLD = 0.2


def read_hplc(path):
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding_errors="replace")
    cols = list(df.columns)
    if not any(str(c).strip().lower().startswith("time") for c in cols):
        cols[0] = "Time"
        df.columns = cols
    traces, time = {}, None
    for c in cols:
        name = str(c).strip()
        low = name.lower()
        if low.startswith("time"):
            time = pd.to_numeric(df[c], errors="coerce").to_numpy(float)
            continue
        if low.startswith("unnamed") or time is None:
            continue
        y = pd.to_numeric(df[c], errors="coerce").to_numpy(float)
        ok = np.isfinite(time)
        order = np.argsort(time[ok], kind="stable")
        traces[name] = (time[ok][order], y[ok][order])
    return traces


def prep_signal(y):
    y = y - np.nanpercentile(y, BASELINE_PERCENTILE)
    m = np.nanmax(y)
    if np.isfinite(m) and m != 0:
        y = y / m
    if SMOOTH_WINDOW >= 3:
        y = pd.Series(y).rolling(window=SMOOTH_WINDOW, center=True, min_periods=1).mean().values
    return np.asarray(y, dtype=float)


def peak_metrics(t, y):
    y = np.nan_to_num(y, nan=0.0)
    if y.size == 0:
        return np.nan, np.nan
    y_max = float(np.max(y))
    t_max = float(t[np.argmax(y)])
    total = float(np.trapezoid(y, t))
    if y_max <= 0 or total <= 0:
        return t_max, 0.0
    above = y > PEAK_THRESHOLD * y_max
    areas, i, n = [], 0, len(y)
    while i < n:
        if above[i]:
            j = i
            while j + 1 < n and above[j + 1]:
                j += 1
            areas.append(float(np.trapezoid(y[i:j + 1], t[i:j + 1])))
            i = j + 1
        else:
            i += 1
    return t_max, (max(areas) / total if areas else 0.0)


def title_text(name):
    s = re.sub(r"(?i)\b(?:15N|N15)\b", r"$^{15}$N", name)
    return re.sub(r"(?<=[A-Za-z\)])(\d+)(?!\d)", r"$_{\1}$", s)


def plot_trace(name, t, y, t_r):
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for side in ("left", "right", "top", "bottom"):
        ax.spines[side].set_linewidth(5)
    ax.set_box_aspect(1.5 / 1.8)
    ax.plot(t, y, lw=6.0, color="#1f77b4")
    ax.set_title(title_text(name), fontsize=30, pad=20)
    ax.set_xlabel("Time (min)", fontsize=26)
    ax.set_ylabel("Nor. Int. (a.u.)", fontsize=26)
    ax.tick_params(axis="both", which="major", labelsize=26)
    ax.text(0.03, 0.98, f"T$_{{R}}$ = {t_r:.1f} min", transform=ax.transAxes,
            va="top", ha="left", fontsize=26,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#cccccc", alpha=0.8))
    ax.grid(alpha=0.3, ls="--")
    ax.set_xlim(X_START, X_END)
    ax.set_xticks(np.arange(X_START, X_END + 1e-9, 10.0))
    ax.set_yticks(np.arange(0.0, 1.1, 0.5))
    ax.set_ylim(-0.1, 1.1)
    fig.tight_layout()
    return fig


def main():
    paths = sys.argv[1:]
    if not paths:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        paths = list(filedialog.askopenfilenames(title="HPLC data (one or more CSV files)"))
        root.destroy()
    if not paths:
        raise SystemExit("cancelled")

    outdir = Path(paths[0]).parent / "hplc_output"
    outdir.mkdir(exist_ok=True)
    traces, source = {}, {}
    for p in paths:
        for name, tr in read_hplc(Path(p)).items():
            if name in traces:
                raise SystemExit(f"'{name}' appears in both {source[name]} and {Path(p).name}; "
                                 "rename one of them.")
            traces[name], source[name] = tr, Path(p).name

    rows = []
    with PdfPages(outdir / "hplc_chromatograms.pdf") as pdf:
        for name, (t, raw) in traces.items():
            win = (t >= X_START) & (t <= X_END)
            t_w = t[win]
            y = prep_signal(raw[win])
            t_r, main_frac = peak_metrics(t_w, y)
            fig = plot_trace(name, t_w, y, t_r)
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
            fig.savefig(outdir / f"{safe}_chrom.png", dpi=300)
            pdf.savefig(fig)
            plt.close(fig)
            rows.append({"construct": name, "retention_time_min": t_r,
                         "main_peak_area_fraction": main_frac})

    pd.DataFrame(rows).sort_values("construct").to_csv(outdir / "hplc_summary.csv", index=False)
    print(f"{len(rows)} chromatograms -> {outdir.resolve()}")


if __name__ == "__main__":
    main()
