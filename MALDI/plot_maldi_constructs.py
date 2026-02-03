import os
import sys
from typing import Dict, Optional, Tuple, List

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import re
import unicodedata

SPECTRA_CSV = "maldi_all_spectra.csv"
THEORETICAL_CSV = "maldi_all_theoretical.csv"
OUTPUT_DIR = "plots-MALDI"

# X-axis range restriction
XRANGE_MIN = 10000.0
XRANGE_MAX = 16200.0

# Optional hardcoded theoretical values provided by user
HARDCODED_THEORETICAL = {
    "GGG": 13787.21, "GGA": 13801.23, "GGL": 13843.32, "GGS": 13817.23,
    "GAG": 13801.23, "GAA": 13815.26, "GAL": 13857.34, "GAS": 13831.26,
    "GLG": 13843.32, "GLA": 13857.34, "GLL": 13899.42, "GLS": 13873.34,
    "GSG": 13817.23, "GSA": 13831.26, "GSL": 13873.34, "GSS": 13847.26,
    "AGG": 13801.23, "AGA": 13815.26, "AGL": 13857.34, "AGS": 13831.26,
    "AAG": 13815.26, "AAA": 13829.29, "AAL": 13871.37, "AAS": 13845.29,
    "ALG": 13857.34, "ALA": 13871.37, "ALL": 13913.45, "ALS": 13887.37,
    "ASG": 13831.26, "ASA": 13845.29, "ASL": 13887.37, "ASS": 13861.29,
    "LGG": 13843.32, "LGA": 13857.34, "LGL": 13899.42, "LGS": 13873.34,
    "LAG": 13857.34, "LAA": 13871.37, "LAL": 13913.45, "LAS": 13887.37,
    "LLG": 13899.42, "LLA": 13913.45, "LLL": 13955.53, "LLS": 13929.45,
    "LSG": 13873.34, "LSA": 13887.37, "LSL": 13929.45, "LSS": 13903.37,
    "SGG": 13817.23, "SGA": 13831.26, "SGL": 13873.34, "SGS": 13847.26,
    "SAG": 13831.26, "SAA": 13845.29, "SAL": 13887.37, "SAS": 13861.29,
    "SLG": 13873.34, "SLA": 13887.37, "SLL": 13929.45, "SLS": 13903.37,
    "SSG": 13847.26, "SSA": 13861.29, "SSL": 13903.37, "SSS": 13877.29,
}

# Font sizes
TITLE_FONTSIZE = 22
LABEL_FONTSIZE = 18
TICK_FONTSIZE = 14
ANNOTATION_FONTSIZE = 14


def _strip_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df


def safe_stem(name: str) -> str:
    """Sanitize a string for use as a safe filename stem on Windows.
    - Normalize unicode to NFKD and strip combining marks
    - Replace any character not in [A-Za-z0-9._-] with underscore
    - Collapse multiple underscores and strip leading/trailing underscores/dots/spaces
    """
    norm = unicodedata.normalize("NFKD", name)
    # remove combining marks
    norm = "".join(ch for ch in norm if not unicodedata.combining(ch))
    # replace invalids
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", norm)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._ ")
    # Avoid empty
    return cleaned or "plot"


def read_spectra(path: str) -> Tuple[pd.DataFrame, List[str], Dict[str, Tuple[str, str]]]:
    df = pd.read_csv(path)
    df = _strip_cols(df)

    cols = list(df.columns)
    cols_lower = [c.lower().strip() for c in cols]
    lower_to_orig: Dict[str, str] = {c.lower().strip(): c for c in cols}

    def is_mz(col: str) -> bool:
        return col.lower().strip().startswith("m_z_")

    def mz_id(col: str) -> str:
        return col.split("m_z_", 1)[1].strip()

    def is_intensity(col: str) -> bool:
        cl = col.lower().strip()
        return cl.startswith("intensity_") or cl == "intensity"

    # Build mapping construct -> (mz_col, int_col) using robust pairing rules
    pairs: Dict[str, Tuple[str, str]] = {}
    n = len(cols)
    for i, col in enumerate(cols):
        if not is_mz(col):
            continue
        cid = mz_id(col)
        # Preferred: find exact matching intensity_<cid> (case-insensitive)
        cand_key = f"intensity_{cid.lower()}"
        int_col = None
        if cand_key in lower_to_orig:
            int_col = lower_to_orig[cand_key]
        else:
            # Next, if the immediate next column looks like an intensity column, accept it
            if i + 1 < n and is_intensity(cols[i + 1]):
                int_col = cols[i + 1]
            else:
                # Finally, scan for any intensity_ prefix whose suffix matches cid (case-insensitive)
                for c in cols:
                    if c == col:
                        continue
                    if c.lower().strip().startswith("intensity_"):
                        suf = c.split("intensity_", 1)[1].strip()
                        if suf.lower() == cid.lower():
                            int_col = c
                            break
        if int_col is not None:
            pairs[cid] = (col, int_col)

    constructs = sorted(pairs.keys())
    if not constructs:
        raise ValueError("No constructs found. Expect columns like m_z_<ID> with an adjacent or matching intensity column.")

    return df, constructs, pairs


def _normalize_name_for_match(s: str) -> str:
    """Normalize a construct name for robust matching.
    - strip spaces
    - within parentheses, replace underscores with slashes (e.g., (V_A_K) -> (V/A/K))
    - lower-case for case-insensitive comparison
    """
    s2 = str(s)
    # remove zero-width and BOM-like format chars
    s2 = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", s2)
    s2 = s2.strip().replace(" ", "")
    # Replace underscores with slashes inside any (...) group
    def _paren_fix(m: re.Match) -> str:
        inner = m.group(1)
        return f"({inner.replace('_', '/')} )" if False else f"({inner.replace('_', '/')})"
    s2 = re.sub(r"\(([^)]*)\)", _paren_fix, s2)
    return s2.lower()


def try_read_theoretical_table(path: str) -> pd.DataFrame:
    """Robustly read the theoretical table from CSV/Excel.

    Tries multiple encodings, engines, and delimiters. Falls back to Excel readers
    if the file is actually an .xlsx/.xls despite the extension.
    """
    # Try CSV with various encodings/engines/sep
    encodings = [None, "utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"]
    seps = [None, ",", ";", "\t", "|"]
    errors = []
    for enc in encodings:
        for sep in seps:
            for engine in ("c", "python"):
                try:
                    df = pd.read_csv(path, encoding=enc, engine=engine, sep=sep)
                    return _strip_cols(df)
                except Exception as e:
                    errors.append(f"enc={enc}, sep={sep}, engine={engine}: {e}")
                    continue

    # Try reading as Excel (supports misnamed files)
    try:
        df = pd.read_excel(path, engine="openpyxl")
        return _strip_cols(df)
    except Exception as e_xlsx:
        errors.append(f"read_excel(openpyxl): {e_xlsx}")
    try:
        df = pd.read_excel(path)  # fallback to default engine
        return _strip_cols(df)
    except Exception as e_xls_any:
        errors.append(f"read_excel(default): {e_xls_any}")

    raise RuntimeError("Failed to read theoretical table after multiple attempts.\n" + "\n".join(errors))


def build_theoretical_map(df_th: pd.DataFrame, constructs: List[str]) -> Dict[str, Optional[float]]:
    # Normalize columns
    cols_lower = {c: c.lower().strip() for c in df_th.columns}
    lower_to_orig = {v: k for k, v in cols_lower.items()}
    df_th_norm = df_th.rename(columns=cols_lower)

    # Common candidate column names
    name_cols = [c for c in df_th_norm.columns if any(k in c for k in ("construct", "name", "id", "sample", "variant"))]
    mz_cols = [c for c in df_th_norm.columns if ("theor" in c or "theoretical" in c or "mz" in c or "m/z" in c or "mass" in c)]

    mapping: Dict[str, Optional[float]] = {k: None for k in constructs}
    # Build a normalized lookup for construct names
    norm_to_orig: Dict[str, str] = {}
    for c in constructs:
        norm_to_orig[_normalize_name_for_match(c)] = c

    # Case 1: long format with columns like [construct, theoretical_mz]
    if name_cols and mz_cols and len(df_th_norm) >= 1:
        # Pick the most likely theoretical column (prefer one with theor in name)
        mz_col = None
        for c in mz_cols:
            if "theor" in c or "theoretical" in c:
                mz_col = c
                break
        if mz_col is None:
            # fallback to the first mz-like column
            mz_col = mz_cols[0]

        name_col = name_cols[0]
        for _, row in df_th_norm[[name_col, mz_col]].dropna().iterrows():
            key_raw = str(row[name_col]).strip()
            key_norm = _normalize_name_for_match(key_raw)
            val = row[mz_col]
            # Coerce theoretical value, handling thousands separators
            try:
                val_num = pd.to_numeric(str(val).replace(",", ""), errors="coerce")
            except Exception:
                val_num = pd.NA
            if pd.notna(val_num) and key_norm in norm_to_orig:
                orig = norm_to_orig[key_norm]
                mapping[orig] = float(val_num)
        # If we filled many values, return
        if any(v is not None for v in mapping.values()):
            return mapping

    # Case 2: wide format with columns like theoretical_<ID> or <ID>
    # Build an index over theoretical columns
    th_cols_by_id: Dict[str, str] = {}
    for c in df_th_norm.columns:
        base = c.lower().strip()
        for cid in constructs:
            cid_lower = cid.lower().strip()
            # Accept matches like '<cid>', 'theoretical_<cid>', 'mz_<cid>', 'm_z_<cid>'
            candidates = [cid_lower, f"theoretical_{cid_lower}", f"theor_{cid_lower}", f"mz_{cid_lower}", f"m_z_{cid_lower}"]
            if any(base == cand for cand in candidates) or base.endswith(f"_{cid_lower}"):
                th_cols_by_id[cid] = c
                break

    if th_cols_by_id:
        # If the file has multiple rows, take the first non-null value per column
        for cid, col in th_cols_by_id.items():
            series = pd.to_numeric(df_th_norm[col], errors="coerce").dropna()
            mapping[cid] = float(series.iloc[0]) if not series.empty else None
        return mapping

    # If none matched, return None for all; downstream will handle as N/A
    return mapping


def format_annotation(obs: Optional[float], theo: Optional[float]) -> str:
    parts = []
    if obs is not None:
        parts.append(f"m/z observed: {obs:.3f}")
    else:
        parts.append("m/z observed: N/A")
    if theo is not None:
        parts.append(f"m/z theoretical: {theo:.3f}")
    else:
        parts.append("m/z theoretical: N/A")
    if obs is not None and theo is not None:
        delta = obs - theo
        try:
            pct = (delta / theo) * 100 if theo != 0 else float("nan")
        except Exception:
            pct = float("nan")
        parts.append(f"Delta: {delta:+.3f} Da")
        parts.append(f"Error: {pct:+.3f} %")
    else:
        parts.append("Delta: N/A")
        parts.append("Error: N/A")
    return "\n".join(parts)


def plot_construct(df: pd.DataFrame, construct: str, mz_col: str, int_col: str, theoretical_mz: Optional[float], out_dir: str,
                   figsize: Tuple[float, float] = (6.0, 5.0), dpi: int = 200) -> str:
    s_mz = pd.to_numeric(df[mz_col], errors="coerce")
    s_int = pd.to_numeric(df[int_col], errors="coerce")
    mask = s_mz.notna() & s_int.notna()
    s_mz = s_mz[mask]
    s_int = s_int[mask]

    if s_int.empty:
        # Nothing to plot
        return ""

    # Restrict to requested x-range for plotting and observed peak calculation
    in_range = (s_mz >= XRANGE_MIN) & (s_mz <= XRANGE_MAX)
    s_mz_plot = s_mz[in_range]
    s_int_plot = s_int[in_range]

    obs_mz: Optional[float] = None
    if not s_int_plot.empty:
        idx_max = s_int_plot.idxmax()
        obs_mz = float(df.loc[idx_max, mz_col]) if pd.notna(df.loc[idx_max, mz_col]) else None

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Plot only within the requested range
    ax.plot(s_mz_plot, s_int_plot, color="#FF8C00", linewidth=1.2)  # dark orange

    if obs_mz is not None:
        # Use a contrasting color for the dashed m/z max line
        ax.axvline(obs_mz, color="#1f77b4", linestyle="--", linewidth=1.2, alpha=0.95, label="m/z max")

    ax.set_title(construct, fontsize=TITLE_FONTSIZE)
    ax.set_xlabel("m/z", fontsize=LABEL_FONTSIZE)
    ax.set_ylabel("Intensity", fontsize=LABEL_FONTSIZE)
    ax.tick_params(axis='both', labelsize=TICK_FONTSIZE)
    ax.set_xlim(XRANGE_MIN, XRANGE_MAX)

    # Annotation at top-right
    text = format_annotation(obs_mz, theoretical_mz)
    # Place annotation at the top-left: draw text, then a rounded rectangle BEHIND it so it doesn't block the curve
    txt = ax.text(
        0.01, 0.98, text, transform=ax.transAxes, ha="left", va="top",
        fontsize=ANNOTATION_FONTSIZE, color="black", zorder=3.5
    )
    # Force a draw to compute text size, then create a low-zorder background patch
    try:
        fig.canvas.draw()  # needed to get accurate text bounding box
        renderer = fig.canvas.get_renderer()
        tb = txt.get_window_extent(renderer=renderer).expanded(1.05, 1.10)
        # Convert to axes coordinates
        tb_axes = tb.transformed(ax.transAxes.inverted())
        rect = mpatches.FancyBboxPatch(
            (tb_axes.x0, tb_axes.y0), tb_axes.width, tb_axes.height,
            transform=ax.transAxes,
            boxstyle="round,pad=0.3",
            facecolor="white", edgecolor="none", linewidth=0.0, alpha=0.6,
            zorder=0.5,
        )
        ax.add_patch(rect)
        # Ensure text stays on top of the patch
        txt.set_zorder(3.5)
    except Exception:
        # If anything goes wrong, fall back silently (text without background)
        pass

    # Tight layout and save
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{safe_stem(construct)}.png")
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    # Figure size ratio 1.8:1.5 -> simplify to 6:5 inches
    figsize = (6.0, 5.0)

    spectra_csv = SPECTRA_CSV
    theoretical_csv = THEORETICAL_CSV

    if not os.path.exists(spectra_csv):
        print(f"ERROR: '{spectra_csv}' not found in working directory {os.getcwd()}", file=sys.stderr)
        sys.exit(1)

    df_spec, constructs, col_pairs = read_spectra(spectra_csv)

    # Map construct -> theoretical mz
    # Start with provided theoretical map
    theoretical_map: Dict[str, Optional[float]] = {c: HARDCODED_THEORETICAL.get(c) for c in constructs}
    if os.path.exists(theoretical_csv):
        try:
            # Only supplement missing entries from file
            df_th = try_read_theoretical_table(theoretical_csv)
            supplemental = build_theoretical_map(df_th, constructs)
            for k, v in supplemental.items():
                if theoretical_map.get(k) is None and v is not None:
                    theoretical_map[k] = v
        except Exception as e:
            print(f"WARNING: Failed to read theoretical CSV: {e}", file=sys.stderr)

    # Plot each construct
    outputs = []
    for construct in constructs:
        mz_col, int_col = col_pairs.get(construct, (None, None))
        if mz_col is None or int_col is None:
            continue
        out = plot_construct(
            df_spec,
            construct,
            mz_col,
            int_col,
            theoretical_map.get(construct),
            OUTPUT_DIR,
            figsize=figsize,
            dpi=220,
        )
        if out:
            outputs.append(out)

    print(f"Saved {len(outputs)} plot(s) to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
