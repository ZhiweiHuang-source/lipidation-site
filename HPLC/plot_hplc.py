import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import re


def _read_hplc_csv(path: Path) -> pd.DataFrame:
    """Read an HPLC CSV page and return a DataFrame with a canonical 'Time' column.

    Handles odd encodings like 'Time�(min)'. Keeps all other columns as-is.
    """
    if not path.exists():
        raise FileNotFoundError(f"HPLC file not found: {path}")

    # Try utf-8-sig first then fallback with replacement to be robust
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding_errors="replace")

    # Find time column
    time_col = None
    for c in df.columns:
        cn = str(c).strip().lower()
        if cn.startswith("time"):
            time_col = c
            break
    if time_col is None:
        # Assume first column is time
        time_col = df.columns[0]
    df = df.rename(columns={time_col: "Time"})
    # Coerce to numeric time
    df["Time"] = pd.to_numeric(df["Time"], errors="coerce")
    # Drop any other columns that look like time columns or unnamed placeholders
    keep_cols = ["Time"]
    for c in df.columns:
        if c == "Time":
            continue
        cn = str(c).strip().lower()
        if cn.startswith("time"):
            # skip duplicate time-like columns (e.g., 'time (min).1')
            continue
        if cn.startswith("unnamed"):
            # skip pandas unnamed columns
            continue
        keep_cols.append(c)
    df = df[keep_cols]
    df = df.dropna(subset=["Time"]).reset_index(drop=True)
    return df


def _get_multi_time_overrides(path: Path) -> Dict[str, np.ndarray]:
    """Detects if a CSV contains multiple time columns and returns a mapping of
    construct name -> alternate time vector for constructs that use the second time.

    This is specifically to support Page 3 where K80, m-K80, V80, m-V80, V40, m-V40
    are recorded against a second time axis (column J in Excel).
    """
    overrides: Dict[str, np.ndarray] = {}
    if not path or not path.exists():
        return overrides
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = pd.read_csv(path, encoding_errors="replace")

    # Find indices of time-like columns
    time_cols: List[int] = []
    for idx, c in enumerate(raw.columns):
        cn = str(c).strip().lower()
        if cn.startswith("time"):
            time_cols.append(idx)
    if len(time_cols) < 2:
        return overrides

    # Use first and second time columns
    t1_idx, t2_idx = time_cols[0], time_cols[1]
    # Build time vectors as float arrays
    t2 = pd.to_numeric(raw.iloc[:, t2_idx], errors="coerce").to_numpy(dtype=float)

    # Constructs that should use the second time axis are to the right of t2_idx
    right_cols = [str(c) for c in list(raw.columns)[t2_idx + 1 :]]
    # Only include non-empty, non-unnamed columns
    right_cols = [c for c in right_cols if c and not str(c).strip().lower().startswith("unnamed")]

    # Normalize names similarly to display cleaning (no rename, keep exact header)
    for name in right_cols:
        overrides[name] = t2
    return overrides

def _merge_pages(page1: pd.DataFrame, page2: pd.DataFrame) -> pd.DataFrame:
    """Merge two page DataFrames on Time via outer join and sort by Time.

    Columns from both are kept; duplicate construct names across pages are averaged.
    """
    # Merge on Time
    df = pd.merge(page1, page2, on="Time", how="outer", suffixes=("_p1", "_p2"))
    df = df.sort_values("Time").reset_index(drop=True)

    # Build unified columns: prefer averaging columns that appear with _p1/_p2 or duplicates
    cols = [c for c in df.columns if c != "Time"]
    # Map base names to list of actual columns
    groups: Dict[str, List[str]] = {}
    for c in cols:
        base = str(c)
        # strip page suffixes if present
        if base.endswith("_p1"):
            base = base[:-3]
        elif base.endswith("_p2"):
            base = base[:-3]
        groups.setdefault(base, []).append(c)

    out = {"Time": df["Time"].values}
    for base, members in groups.items():
        # Row-wise average across members (ignoring NaNs)
        vals = df[members].astype(float)
        out[base] = vals.mean(axis=1, skipna=True).values
    merged = pd.DataFrame(out)
    return merged


def _merge_pages_multi(pages: List[pd.DataFrame]) -> pd.DataFrame:
    """Merge 2+ HPLC page DataFrames on Time and average duplicate construct columns.

    - All pages are outer-merged on 'Time'.
    - Non-Time columns are temporarily suffixed with _p{idx} to disambiguate.
    - After merging, duplicate base construct names (stripped of _p\\d+ suffix) are averaged row-wise.
    """
    assert pages, "No pages provided"
    # Normalize each page: ensure Time column and suffix non-Time columns
    norm_pages: List[pd.DataFrame] = []
    for i, df in enumerate(pages, start=1):
        df = df.copy()
        # Ensure 'Time' column
        if "Time" not in df.columns:
            raise ValueError("All pages must have a 'Time' column after _read_hplc_csv")
        # Suffix non-Time columns with _p{i}
        rename_map = {c: f"{c}_p{i}" for c in df.columns if c != "Time"}
        df = df.rename(columns=rename_map)
        norm_pages.append(df)
    # Outer-merge all on Time
    merged = norm_pages[0]
    for df in norm_pages[1:]:
        merged = pd.merge(merged, df, on="Time", how="outer")
    merged = merged.sort_values("Time").reset_index(drop=True)
    # Average duplicate bases across pages
    cols = [c for c in merged.columns if c != "Time"]
    groups: Dict[str, List[str]] = {}
    import re as _re
    for c in cols:
        base = _re.sub(r"_p\d+$", "", str(c))
        groups.setdefault(base, []).append(c)
    out = {"Time": merged["Time"].values}
    for base, members in groups.items():
        vals = merged[members].astype(float)
        out[base] = vals.mean(axis=1, skipna=True).values
    return pd.DataFrame(out)


def _prep_signal(y: np.ndarray, baseline_percentile: float = 1.0, normalize: bool = True,
                 smooth_window: int = 0) -> np.ndarray:
    """Baseline-correct and optionally normalize/smooth the signal.

    - Baseline subtracts the given percentile to reduce negative baselines.
    - Normalize scales max to 1 after baseline.
    - Smooth applies a centered rolling mean if smooth_window >= 3 (odd recommended).
    """
    y = np.asarray(y, dtype=float)
    if np.all(np.isnan(y)):
        return y
    base = np.nanpercentile(y, baseline_percentile)
    yb = y - base
    if normalize:
        m = np.nanmax(yb) if np.isfinite(np.nanmax(yb)) else 1.0
        if m != 0:
            yb = yb / m
    if smooth_window and smooth_window >= 3:
        # Use pandas rolling for simplicity
        yb = pd.Series(yb).rolling(window=smooth_window, center=True, min_periods=1).mean().values
    return np.asarray(yb, dtype=float)


def _peak_metrics(time: np.ndarray, y: np.ndarray, threshold_frac: float = 0.2) -> Dict[str, float]:
    """Compute simple chromatogram metrics: t_max, max, n_peaks, main_peak_area_frac.

    Peaks are contiguous regions where y > threshold_frac * max(y) after baseline/normalization.
    Area is trapezoidal integration over Time.
    """
    if len(time) == 0 or np.all(~np.isfinite(y)):
        return {"t_max": np.nan, "y_max": np.nan, "n_peaks": 0, "main_peak_area_frac": np.nan}
    y = np.nan_to_num(y, nan=0.0)
    y_max = float(np.max(y)) if y.size else 0.0
    t_max = float(time[np.argmax(y)]) if y.size else np.nan
    if y_max <= 0:
        return {"t_max": t_max, "y_max": y_max, "n_peaks": 0, "main_peak_area_frac": 0.0}
    mask = y > (threshold_frac * y_max)
    # Find contiguous segments
    segs: List[Tuple[int, int]] = []
    i = 0
    n = len(y)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            segs.append((i, j))
            i = j + 1
        else:
            i += 1
    # Compute areas
    # Use numpy.trapezoid to avoid deprecation warnings
    total_area = float(np.trapezoid(y, time))
    if total_area <= 0:
        return {"t_max": t_max, "y_max": y_max, "n_peaks": len(segs), "main_peak_area_frac": 0.0}
    areas = []
    for (a, b) in segs:
        areas.append(float(np.trapezoid(y[a:b + 1], time[a:b + 1])))
    main_frac = float(max(areas) / total_area) if areas else 0.0
    return {"t_max": t_max, "y_max": y_max, "n_peaks": len(segs), "main_peak_area_frac": main_frac}


def plot_hplc(
    page1_path: Path,
    page2_path: Path,
    outdir: Path,
    page3_path: Optional[Path] = None,
    page4_path: Optional[Path] = None,
    normalize: bool = True,
    smooth_window: int = 5,
    pdf: bool = True,
    threshold_frac: float = 0.2,
    x_start: float = 20.0,
    x_end: float = 40.0,
):
    outdir.mkdir(parents=True, exist_ok=True)

    # Read each page separately so we can keep track of which constructs came from which file
    page1_df = _read_hplc_csv(page1_path)
    page2_df = _read_hplc_csv(page2_path)
    pages = [page1_df, page2_df]

    page1_constructs = {c for c in page1_df.columns if c != "Time"}
    page2_constructs = {c for c in page2_df.columns if c != "Time"}
    page3_constructs: set[str] = set()

    # Optionally include additional pages if provided and exist
    # Keep track of renames to update time_overrides keys later
    p3_renames: Dict[str, str] = {}

    for idx, extra in enumerate((page3_path, page4_path), start=3):
        if extra is not None:
            try:
                if extra.exists():
                    df_extra = _read_hplc_csv(extra)
                    
                    # Disambiguate Page 3 columns that collide with Page 1/2
                    # (e.g., SSS, LLL, SAS, SLL) so they aren't merged (averaged).
                    if idx == 3:
                        p1_p2_cols = page1_constructs | page2_constructs
                        new_cols = {}
                        for c in df_extra.columns:
                            if c == "Time":
                                continue
                            if c in p1_p2_cols:
                                new_name = f"{c}_p3distinct"
                                new_cols[c] = new_name
                                p3_renames[c] = new_name
                        if new_cols:
                            df_extra = df_extra.rename(columns=new_cols)

                    pages.append(df_extra)
                    if idx == 3:
                        page3_constructs = {c for c in df_extra.columns if c != "Time"}
            except Exception:
                pass

    # Detect alternate time vector overrides from any extra page that has multiple time columns
    time_overrides: Dict[str, np.ndarray] = {}
    for extra_path in (page3_path, page4_path):
        if extra_path is not None and extra_path.exists():
            try:
                ov = _get_multi_time_overrides(extra_path)
                # If this is Page 3, apply the renames to the keys
                if extra_path == page3_path and p3_renames:
                    renamed_ov = {}
                    for k, v in ov.items():
                        # If k was renamed, use new name, else keep k
                        new_k = p3_renames.get(k, k)
                        renamed_ov[new_k] = v
                    ov = renamed_ov
                
                # Later pages win in case of overlap
                time_overrides.update(ov)
            except Exception:
                pass

    merged = _merge_pages_multi(pages) if len(pages) > 2 else _merge_pages(pages[0], pages[1])

    time = np.asarray(merged["Time"].values, dtype=float)
    construct_cols = [c for c in merged.columns if c != "Time"]

    # Prepare PDF writer if requested
    pdf_path = outdir / "hplc_chromatograms.pdf"
    pdf_writer = PdfPages(str(pdf_path)) if pdf else None

    summary_rows = []

    def _clean_construct_name(name: str) -> str:
        """Clean up construct/column names for display.

        - Remove prefixes like 'HPLC chromatogram - ' (case-insensitive, optional dash/space)
        - Trim surrounding whitespace and separators
        """
        s = str(name)
        # Remove suffix used for disambiguation
        s = s.replace("_p3distinct", "")
        # Strip any leading 'HPLC chromatogram[s]' with optional spaces and dash
        s = re.sub(r"(?i)^\s*HPLC\s*chromatogram[s]?\s*[-:]*\s*", "", s)
        # Final tidy of stray separators
        s = s.strip().strip("-:")
        return s.strip()

    def _apply_label_aliases(label: str) -> str:
        """Apply human-friendly aliases for certain labels without changing filenames.

        Rules (case-insensitive):
        - 'm[-_\s]*k80'  -> 'm-(V/A/K)80'
        - standalone 'k80' -> '(V/A/K)80'
        """
        s = label
        # m-k80 first to avoid double-applying
        s = re.sub(r"(?i)\bm[-_\s]*k80\b", "m-(V/A/K)80", s)
        s = re.sub(r"(?i)\bk80\b", "(V/A/K)80", s)
        return s

    def _format_title_subscripts(name: str) -> str:
        """Format specific numbers as subscripts in the title using mathtext.

        Replaces standalone occurrences of 30, 40, or 80 with $_{..}$ so e.g.,
        'K80' becomes 'K$_{80}$', 'm-V40' becomes 'm-V$_{40}$'.
        """
        s = str(name)
        # Only subscript 30/40/80 when not part of a longer number
        s = re.sub(r"(?<!\d)(30|40|80)(?!\d)", r"$_{\1}$", s)
        return s

    def _format_display_name(raw_name: str, in_page1: bool, in_page2: bool, in_page3: bool) -> str:
        """Page-aware display formatter.

        - Page 1 & 2: 3-letter constructs become m-[XXX]-V30.
        - Page 3: "N15" becomes $^{15}$N; 3-letter constructs become [XXX]-V30.
        - Then apply aliases and subscripts.
        """
        name = _clean_construct_name(raw_name)
        # Check if name is strictly 3 letters (ignoring case/whitespace which is already cleaned)
        is_strictly_three_letters = bool(re.fullmatch(r"[A-Za-z]{3}", name))

        if in_page3 and re.search(r"(?i)N15", name):
            name = re.sub(r"(?i)N15", r"$^{15}$N", name)

        if in_page3 and is_strictly_three_letters:
            name = f"[{name}]-V30"
        elif (in_page1 or in_page2) and is_strictly_three_letters:
            name = f"m-[{name}]-V30"

        name = _apply_label_aliases(name)
        name = _format_title_subscripts(name)
        return name

    for col in construct_cols:
        raw = np.asarray(merged[col].astype(float).values, dtype=float)
        # Choose the appropriate time vector: per-construct override (from page 3) or the merged Time
        t_vec = None
        if col in time_overrides:
            t_vec = np.asarray(time_overrides[col], dtype=float)
        else:
            t_vec = time
        # Align lengths defensively in case of merges; trim to shortest
        n = int(min(len(raw), len(t_vec)))
        raw = raw[:n]
        t_vec = t_vec[:n]
        # Restrict to the analysis window [x_start, x_end] for preprocessing and metrics
        mask = (t_vec >= float(x_start)) & (t_vec <= float(x_end))
        time_win = np.asarray(t_vec[mask], dtype=float)
        raw_win = np.asarray(raw[mask], dtype=float)
        y = _prep_signal(raw_win, baseline_percentile=1.0, normalize=normalize, smooth_window=smooth_window)
        metrics = _peak_metrics(time_win, y, threshold_frac=threshold_frac)

        # Use a readable size, but enforce the width:height ratio of 1.8:1.5 (~1.2)
        # Figure size here is large enough for readability; the ratio is enforced on the axes.
        fig, ax = plt.subplots(figsize=(6.5, 5))
        # Thicken the frame spines for better visibility
        for side in ("left", "right", "top", "bottom"):
            try:
                ax.spines[side].set_linewidth(5)
            except Exception:
                pass
        try:
            # set_box_aspect expects height/width
            ax.set_box_aspect(1.5 / 1.8)
        except Exception:
            pass

        # Plot signal; do not include in legend
        ax.plot(time_win, y, lw=6.0, color="#1f77b4")
        # Clean up and format names with page-specific rules
        raw_name_clean = _clean_construct_name(col)
        display_name = _format_display_name(
            raw_name_clean,
            in_page1=col in page1_constructs,
            in_page2=col in page2_constructs,
            in_page3=col in page3_constructs,
        )
        title_text = display_name
        ax.set_title(title_text, fontsize=30, pad=20)
        # Axis labels with units
        ax.set_xlabel("Time (min)", fontsize=26)
        if normalize:
            ax.set_ylabel("Nor. Int. (a.u.)", fontsize=26)
            # Normalized traces shown in [-0.1, 1.1]
            ax.set_ylim(-0.1, 1.1)
        else:
            ax.set_ylabel("Signal (a.u.), baseline-subtracted", fontsize=26)
        # Larger tick labels for readability
        ax.tick_params(axis='both', which='major', labelsize=26)
        # Annotate retention time as T_R with one decimal place
        ann = f"T$_{'{'}R{'}'}$ = {metrics['t_max']:.1f} min"
        # Nudge annotation slightly right to avoid overlapping the frame border
        ax.text(0.03, 0.98, ann, transform=ax.transAxes, va="top", ha="left", fontsize=26,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#cccccc", alpha=0.8))
        ax.grid(alpha=0.3, ls="--")
        # Start x-axis at requested time (minutes)
        try:
            ax.set_xlim(left=float(x_start), right=float(x_end))
        except Exception:
            pass
        # Fixed tick increments
        ax.set_xticks(np.arange(x_start, x_end + 1e-9, 10.0))
        if normalize:
            ax.set_yticks(np.arange(0.0, 1.1, 0.5))
            ax.set_ylim(-0.1, 1.1)
        # No legend requested
        fig.tight_layout()

        # Sanitize filename for portability
        # If the construct was disambiguated with a suffix, include it in the filename to prevent overwrites.
        filename_base = raw_name_clean
        if col.endswith("_p3distinct"):
             filename_base += "_p3distinct"
        
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename_base)
        png_path = outdir / f"{safe_name}_chrom.png"
        fig.savefig(png_path, dpi=300)
        if pdf_writer is not None:
            pdf_writer.savefig(fig)
        plt.close(fig)

        summary_rows.append({
            "construct": col,
            **metrics,
        })

    # Close PDF
    if pdf_writer is not None:
        pdf_writer.close()

    # Write summary CSV
    summary_df = pd.DataFrame(summary_rows).sort_values("construct").reset_index(drop=True)
    summary_df.to_csv(outdir / "hplc_summary.csv", index=False)

    print(f"WROTE: {outdir}")
    if pdf:
        print(f"- multipage PDF: {pdf_path}")
    print(f"- per-construct PNGs and summary CSV")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Plot HPLC chromatograms from two CSV pages and summarize purity metrics.")
    ap.add_argument("--page1", type=Path, default=Path("Analytical HPLC page 1.csv"), help="CSV file for page 1")
    ap.add_argument("--page2", type=Path, default=Path("Analytical HPLC page 2.csv"), help="CSV file for page 2")
    ap.add_argument("--outdir", type=Path, default=Path("outputs/hplc_plots"), help="Directory to write outputs")
    ap.add_argument("--page3", type=Path, default=None, help="Optional CSV file for page 3")
    ap.add_argument("--page4", type=Path, default=None, help="Optional CSV file for page 4")
    ap.add_argument("--no-normalize", action="store_true", help="Disable normalization to max=1")
    ap.add_argument("--smooth-window", type=int, default=5, help="Centered rolling window for smoothing; 0=off")
    ap.add_argument("--no-pdf", action="store_true", help="Do not write the multipage PDF")
    ap.add_argument("--threshold-frac", type=float, default=0.2, help="Threshold fraction of max for peak segmentation (0-1)")
    ap.add_argument("--x-start", type=float, default=20.0, help="Left x-axis limit in minutes (default 20)")
    ap.add_argument("--x-end", type=float, default=40.0, help="Right x-axis limit in minutes (default 40)")
    args = ap.parse_args(argv)

    plot_hplc(
        page1_path=args.page1,
        page2_path=args.page2,
        outdir=args.outdir,
        page3_path=args.page3,
        page4_path=args.page4,
        normalize=not args.no_normalize,
        smooth_window=args.smooth_window,
        pdf=not args.no_pdf,
        threshold_frac=args.threshold_frac,
        x_start=args.x_start,
        x_end=args.x_end,
    )


if __name__ == "__main__":
    main()
