import os
from typing import Dict, Optional, List, Tuple

import pandas as pd

# Reuse helpers and constants from existing modules
from plot_maldi_constructs import (
    SPECTRA_CSV,
    THEORETICAL_CSV,
    XRANGE_MIN,
    XRANGE_MAX,
    read_spectra,
    try_read_theoretical_table,
    build_theoretical_map,
)
from plot_maldi_constructs import _normalize_name_for_match  # type: ignore

from plot_maldi_book1 import (
    BOOK1_CSV,
    read_book1,
)
# Import window settings and overrides from book1 module
from plot_maldi_book1 import FIXED_WINDOW_WIDTH, XMIN_OVERRIDES  # type: ignore


def compute_observed_main() -> Dict[str, Optional[float]]:
    """Compute observed m/z max within the standard range using the same
    robust column pairing as the plotting script (handles 'Intensity' and
    case differences like 'Intensity_*')."""
    df, constructs, pairs = read_spectra(SPECTRA_CSV)
    observed: Dict[str, Optional[float]] = {c: None for c in constructs}
    for c in constructs:
        mz_col, int_col = pairs[c]
        s_mz = pd.to_numeric(df[mz_col], errors="coerce")
        s_int = pd.to_numeric(df[int_col], errors="coerce")
        mask = s_mz.notna() & s_int.notna()
        s_mz = s_mz[mask]
        s_int = s_int[mask]
        in_range = (s_mz >= XRANGE_MIN) & (s_mz <= XRANGE_MAX)
        s_mz_plot = s_mz[in_range]
        s_int_plot = s_int[in_range]
        if s_int_plot.empty:
            # Fallback to full span if window has no data
            s_mz_plot = s_mz
            s_int_plot = s_int
        if not s_int_plot.empty:
            idx_max = s_int_plot.idxmax()
            val = s_mz_plot.loc[idx_max]
            observed[c] = float(val) if pd.notna(val) else None
        else:
            observed[c] = None
    return observed


def compute_observed_book1() -> Dict[str, Optional[float]]:
    """Compute observed m/z max within the per-construct Book1 windows."""
    if not os.path.exists(BOOK1_CSV):
        return {}
    pairs = read_book1(BOOK1_CSV)
    result: Dict[str, Optional[float]] = {}
    for name, s_mz, s_int in pairs:
        norm = _normalize_name_for_match(name)
        # Determine x-range window
        if norm in XMIN_OVERRIDES:
            x_min = XMIN_OVERRIDES[norm]
            x_max = x_min + FIXED_WINDOW_WIDTH
        else:
            mz_min = float(s_mz.min())
            mz_max = float(s_mz.max())
            center = (mz_min + mz_max) / 2.0
            half = FIXED_WINDOW_WIDTH / 2.0
            x_min = center - half
            x_max = center + half
        in_window = (s_mz >= x_min) & (s_mz <= x_max)
        s_mz_plot = s_mz[in_window]
        s_int_plot = s_int[in_window]
        if s_int_plot.empty:
            # Fallback to full data if window selection is empty
            s_mz_plot = s_mz
            s_int_plot = s_int
        if not s_int_plot.empty:
            idx_max = s_int_plot.idxmax()
            val = s_mz_plot.loc[idx_max]
            result[name] = float(val) if pd.notna(val) else None
        else:
            result[name] = None
    return result


def _clean_display_name(s: str) -> str:
    """Clean a construct name for display: remove zero-width/BOM, trim, and
    replace underscores with slashes inside parentheses.
    """
    import re as _re
    s2 = _re.sub(r"[\u200b\u200c\u200d\ufeff]", "", str(s))
    s2 = s2.strip()
    def _paren_fix(m):
        inner = m.group(1)
        return f"({inner.replace('_', '/')})"
    s2 = _re.sub(r"\(([^)]*)\)", _paren_fix, s2)
    return s2


def get_construct_names_from_theoretical(df_th: pd.DataFrame) -> List[str]:
    """Extract construct names from a theoretical table using heuristics
    similar to build_theoretical_map.

    Returns a list of unique, stripped names (original casing).
    """
    if df_th is None or df_th.empty:
        return []
    cols_lower = {c: c.lower().strip() for c in df_th.columns}
    df_norm = df_th.rename(columns=cols_lower)
    name_cols = [c for c in df_norm.columns if any(k in c for k in ("construct", "name", "id", "sample", "variant"))]
    names: List[str] = []
    if name_cols:
        col = name_cols[0]
        names = [str(x).strip() for x in df_norm[col].dropna().astype(str).tolist() if str(x).strip()]
    else:
        # Fallback: try to infer from "wide" style by scanning columns that look like construct identifiers
        for c in df_norm.columns:
            base = c.strip()
            if base and not any(k in base.lower() for k in ("theor", "theoretical", "mz", "m/z", "mass", "da", "value", "mw")):
                names.append(base)
    # Deduplicate preserving order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def build_si_table() -> pd.DataFrame:
    obs_main = compute_observed_main()
    obs_book1 = compute_observed_book1()

    # Normalize observed names to coalesce variants
    obs_main_norm: Dict[str, float] = {}
    disp_main_norm: Dict[str, str] = {}
    for k, v in obs_main.items():
        if v is None:
            continue
        nk = _normalize_name_for_match(k)
        obs_main_norm[nk] = v
        disp_main_norm[nk] = _clean_display_name(k)

    obs_book1_norm: Dict[str, float] = {}
    disp_book1_norm: Dict[str, str] = {}
    for k, v in obs_book1.items():
        if v is None:
            continue
        nk = _normalize_name_for_match(k)
        # Only set if not already set by main (prefer main display)
        if nk not in obs_book1_norm:
            obs_book1_norm[nk] = v
            disp_book1_norm[nk] = _clean_display_name(k)

    # Read theoretical and map by normalized names
    theor_by_norm: Dict[str, float] = {}
    disp_theor_norm: Dict[str, str] = {}
    if os.path.exists(THEORETICAL_CSV):
        try:
            df_th = try_read_theoretical_table(THEORETICAL_CSV)
            # Heuristic to find name and theoretical columns (long format)
            cols_lower = {c: c.lower().strip() for c in df_th.columns}
            df_norm = df_th.rename(columns=cols_lower)
            name_cols = [c for c in df_norm.columns if any(k in c for k in ("construct", "name", "id", "sample", "variant"))]
            mz_cols = [c for c in df_norm.columns if ("theor" in c or "theoretical" in c or "mz" in c or "m/z" in c or "mass" in c)]
            if name_cols and mz_cols:
                name_col = name_cols[0]
                # Prefer a column containing 'theor'
                mz_col = next((c for c in mz_cols if "theor" in c or "theoretical" in c), mz_cols[0])
                for _, row in df_norm[[name_col, mz_col]].dropna().iterrows():
                    raw = str(row[name_col]).strip()
                    nk = _normalize_name_for_match(raw)
                    try:
                        val = pd.to_numeric(str(row[mz_col]).replace(",", ""), errors="coerce")
                    except Exception:
                        val = pd.NA
                    if pd.notna(val):
                        theor_by_norm[nk] = float(val)
                        # Only set display once
                        if nk not in disp_theor_norm:
                            disp_theor_norm[nk] = _clean_display_name(raw)
            else:
                # Fallback: attempt through build_theoretical_map over combined keys
                pass
        except Exception:
            pass

    # Union of all normalized keys
    all_norms = set(obs_main_norm.keys()) | set(obs_book1_norm.keys()) | set(theor_by_norm.keys())

    rows: List[Tuple[str, Optional[float], Optional[float], Optional[float], Optional[float]]] = []
    for nk in sorted(all_norms):
        # Choose a nice display name: prefer main, then book1, then theoretical, else normalized key
        if nk in disp_main_norm:
            display = disp_main_norm[nk]
        elif nk in disp_book1_norm:
            display = disp_book1_norm[nk]
        elif nk in disp_theor_norm:
            display = disp_theor_norm[nk]
        else:
            display = nk
        obs = obs_main_norm.get(nk)
        if obs is None:
            obs = obs_book1_norm.get(nk)
        theo = theor_by_norm.get(nk)
        delta = None
        error = None
        if obs is not None and theo is not None:
            delta = obs - theo
            error = (delta / theo) * 100 if theo != 0 else None
        rows.append((display, obs, theo, delta, error))

    df_out = pd.DataFrame(rows, columns=[
        "Construct",
        "m/z observed",
        "m/z theoretical",
        "Delta (Da)",
        "Error (%)",
    ])
    # Round to 3 decimals for presentation
    for col in ["m/z observed", "m/z theoretical", "Delta (Da)", "Error (%)"]:
        df_out[col] = df_out[col].round(3)
    return df_out


def main():
    df = build_si_table()
    out_path = "si_table3.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved SI table with {len(df)} rows: {out_path}")


if __name__ == "__main__":
    main()
