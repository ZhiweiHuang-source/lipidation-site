import os
from typing import List, Tuple, Optional

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Reuse styling and helpers from existing plotting module
from plot_maldi_constructs import (
    safe_stem,
    format_annotation,
    try_read_theoretical_table,
    build_theoretical_map,
    TITLE_FONTSIZE,
    LABEL_FONTSIZE,
    TICK_FONTSIZE,
    ANNOTATION_FONTSIZE,
    THEORETICAL_CSV,
    OUTPUT_DIR,
    XRANGE_MIN,
    XRANGE_MAX,
)
from plot_maldi_constructs import _normalize_name_for_match  # reuse matching normalization

BOOK1_CSV = "Book1.csv"

# Keep a constant x-axis width, but allow different centers per construct
FIXED_WINDOW_WIDTH = XRANGE_MAX - XRANGE_MIN  # e.g., 16200 - 10000 = 6200

# Per-construct x-range overrides (normalized names)
XMIN_OVERRIDES = {
    _normalize_name_for_match("(V/A/K)80"): 32000.0,
    _normalize_name_for_match("m-(V/A/K)80"): 32000.0,
    _normalize_name_for_match("V80"): 32000.0,
    _normalize_name_for_match("m-V80"): 32000.0,
}


def read_book1(path: str) -> List[Tuple[str, pd.Series, pd.Series]]:
    """Read Book1.csv which alternates [m/z, construct] columns.

    Returns a list of tuples: (construct_name, mz_series, intensity_series)
    """
    df = pd.read_csv(path)
    cols = list(df.columns)
    pairs: List[Tuple[str, pd.Series, pd.Series]] = []
    # Expect pattern: col0 = "m/z", col1 = name, col2 = "m/z", col3 = name, ...
    for i in range(1, len(cols), 2):
        name = str(cols[i]).strip()
        # Use positional selection to avoid ambiguity with duplicate 'm/z' headers
        s_mz = pd.to_numeric(df.iloc[:, i - 1], errors="coerce")
        s_int = pd.to_numeric(df.iloc[:, i], errors="coerce")
        # Require both have at least some data
        mask = s_mz.notna() & s_int.notna()
        s_mz = s_mz[mask]
        s_int = s_int[mask]
        if not s_mz.empty and not s_int.empty:
            pairs.append((name, s_mz, s_int))
    return pairs


def plot_pair(name: str, s_mz: pd.Series, s_int: pd.Series, theoretical_mz: Optional[float],
              figsize=(6.0, 5.0), dpi: int = 220) -> Optional[str]:
    # Determine per-construct x-range with fixed width
    norm_name = _normalize_name_for_match(name)
    override_xmin = XMIN_OVERRIDES.get(norm_name)
    if override_xmin is not None:
        x_min = override_xmin
        x_max = x_min + FIXED_WINDOW_WIDTH
    else:
        mz_min = float(s_mz.min())
        mz_max = float(s_mz.max())
        center = (mz_min + mz_max) / 2.0
        half = FIXED_WINDOW_WIDTH / 2.0
        x_min = center - half
        x_max = center + half

    # Limit to window when computing observed max
    in_window = (s_mz >= x_min) & (s_mz <= x_max)
    s_mz_plot = s_mz[in_window]
    s_int_plot = s_int[in_window]
    if s_mz_plot.empty:
        # Fallback to full range if window selection is empty
        s_mz_plot = s_mz
        s_int_plot = s_int
        x_min = float(s_mz_plot.min())
        x_max = x_min + FIXED_WINDOW_WIDTH

    obs_mz: Optional[float] = None
    if not s_int_plot.empty:
        idx_max = s_int_plot.idxmax()
        obs_val = s_mz_plot.loc[idx_max]
        obs_mz = float(obs_val) if pd.notna(obs_val) else None

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.plot(s_mz_plot, s_int_plot, color="#FF8C00", linewidth=1.2)
    if obs_mz is not None:
        ax.axvline(obs_mz, color="#1f77b4", linestyle="--", linewidth=1.2, alpha=0.95)

    ax.set_title(name, fontsize=TITLE_FONTSIZE)
    ax.set_xlabel("m/z", fontsize=LABEL_FONTSIZE)
    ax.set_ylabel("Intensity", fontsize=LABEL_FONTSIZE)
    ax.tick_params(axis="both", labelsize=TICK_FONTSIZE)
    ax.set_xlim(x_min, x_max)

    # Annotation top-left with behind box
    text = format_annotation(obs_mz, theoretical_mz)
    txt = ax.text(
        0.01, 0.98, text, transform=ax.transAxes, ha="left", va="top",
        fontsize=ANNOTATION_FONTSIZE, color="black", zorder=3.5,
    )
    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        tb = txt.get_window_extent(renderer=renderer).expanded(1.05, 1.10)
        tb_axes = tb.transformed(ax.transAxes.inverted())
        rect = mpatches.FancyBboxPatch(
            (tb_axes.x0, tb_axes.y0), tb_axes.width, tb_axes.height,
            transform=ax.transAxes,
            boxstyle="round,pad=0.3",
            facecolor="white", edgecolor="none", linewidth=0.0, alpha=0.6,
            zorder=0.5,
        )
        ax.add_patch(rect)
        txt.set_zorder(3.5)
    except Exception:
        pass

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{safe_stem(name)}.png")
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    if not os.path.exists(BOOK1_CSV):
        raise SystemExit(f"Book1 source not found: {BOOK1_CSV}")

    pairs = read_book1(BOOK1_CSV)
    if not pairs:
        raise SystemExit("No valid [m/z, intensity] pairs found in Book1.csv")

    # Build theoretical map if available
    theoretical_map = {}
    names = [name for name, _, _ in pairs]
    if os.path.exists(THEORETICAL_CSV):
        try:
            df_th = try_read_theoretical_table(THEORETICAL_CSV)
            theoretical_map = build_theoretical_map(df_th, names)
            # Also try to match again with normalized keys in case of formatting variants
            if not any(v is not None for v in theoretical_map.values()):
                # Build a normalization map for Book1 names
                norm_to_name = {_normalize_name_for_match(n): n for n in names}
                # Normalize theoretical table names and fill
                df_norm = df_th.copy()
                if "Constructs" in df_norm.columns:
                    df_norm["Constructs_norm"] = df_norm["Constructs"].apply(_normalize_name_for_match)
                # Try map again using normalized names if possible
                supplemental = build_theoretical_map(df_norm.rename(columns={"Constructs_norm": "Constructs"}), names)
                for k, v in supplemental.items():
                    if theoretical_map.get(k) is None and v is not None:
                        theoretical_map[k] = v
        except Exception:
            theoretical_map = {name: None for name in names}
    else:
        theoretical_map = {name: None for name in names}

    outputs: List[str] = []
    for name, s_mz, s_int in pairs:
        out = plot_pair(name, s_mz, s_int, theoretical_map.get(name))
        if out:
            outputs.append(out)

    print(f"Saved {len(outputs)} Book1 plot(s) to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
