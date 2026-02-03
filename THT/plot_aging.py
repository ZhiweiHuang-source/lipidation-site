import os
import sys
import math
from typing import List, Tuple

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter, MultipleLocator


def _normalize_header(h: str) -> str:
    if not isinstance(h, str):
        return h
    # Replace non-breaking spaces and weird unicode dashes with normal ones
    h = h.replace("\u00A0", " ").replace("\u2011", "-")
    # Strip and collapse internal whitespace
    h = " ".join(h.strip().split())
    return h


def find_group_columns(df: pd.DataFrame, key: str) -> List[str]:
    # Find the first column header containing the key
    # Then take that column and the next two (assuming triplicates in adjacent columns)
    cols = list(df.columns)
    found_idx = -1
    for i, c in enumerate(cols):
        if key in str(c):
            found_idx = i
            break
    
    if found_idx == -1:
        return []
    
    # Return the triplet: found_idx, found_idx+1, found_idx+2
    # Ensure we don't go out of bounds
    group = []
    for j in range(3):
        if found_idx + j < len(cols):
            group.append(cols[found_idx + j])
    return group


def compute_mean_std(df: pd.DataFrame, cols: List[str]) -> Tuple[pd.Series, pd.Series]:
    # Force columns to numeric
    valid_data = []
    for c in cols:
        # Coerce to numeric
        s = pd.to_numeric(df[c], errors='coerce')
        valid_data.append(s)
    
    if not valid_data:
         return pd.Series(dtype=float), pd.Series(dtype=float)

    # Concat into a DataFrame to compute row-wise stats
    subset = pd.concat(valid_data, axis=1)
    return subset.mean(axis=1), subset.std(axis=1)


def style_axes(ax: plt.Axes):
    # Grid: Enabled with alpha=0.3 and style --
    ax.grid(True, alpha=0.3, linestyle='--')
    # Frame Border (Spine) Width: 5
    for spine in ax.spines.values():
        spine.set_linewidth(5)
    # Tick Labels Font Size: 26
    # make the major tick thickness larger (width=5)
    ax.tick_params(axis='both', which='both', labelsize=24, width=5, length=10)
    ax.yaxis.set_major_formatter(ScalarFormatter(useMathText=True))
    ax.ticklabel_format(axis='y', style='sci', scilimits=(3, 3))
    
    # Change x axis increment to 10
    ax.xaxis.set_major_locator(MultipleLocator(10))
    # Change y axis increment to 1 (Assuming same scale logic as GGG, if range permits)
    # But usually aging plot has different range? 
    # Let's check limits. It's THT fluorescence too.
    # We will use auto for Y unless generic 500000 fits. 
    # Let's stick to X increment 10 as requested.
    
    # Box Aspect Ratio: Set to 1.5 / 1.8
    ax.set_box_aspect(1.5 / 1.8)


def plot_aging(csv_path: str, out_path: str):
    # Read CSV, drop empty columns
    df = pd.read_csv(csv_path)
    # Normalize headers
    df.columns = [_normalize_header(c) for c in df.columns]
    # Drop columns that are entirely NaN
    df = df.dropna(axis=1, how='all')

    # Temperature column can be 'Temperature' or typo 'Tmperature'
    temp_col = None
    for cand in ["Temperature", "Tmperature", "Temp", "temperature"]:
        if cand in df.columns:
            temp_col = cand
            break
    if temp_col is None:
        raise ValueError("Could not find a Temperature column in THT_aging.csv")

    # Identify day groups by substring
    # Pass df to new version of find_group_columns
    day1_cols = find_group_columns(df, "LAA_day1")
    day3_cols = find_group_columns(df, "LAA_day3")
    day7_cols = find_group_columns(df, "LAA_day7")

    if not day1_cols or not day3_cols or not day7_cols:
        raise ValueError("Expected columns for LAA_day1, LAA_day3, LAA_day7 not found")

    # Compute mean/std across triplicates
    m1, s1 = compute_mean_std(df, day1_cols)
    m3, s3 = compute_mean_std(df, day3_cols)
    m7, s7 = compute_mean_std(df, day7_cols)

    x = df[temp_col].astype(float)

    # Figure styling: 6.5x5 inches
    plt.rcParams.update({
        'font.size': 26,
        'axes.titlesize': 30,
        'axes.labelsize': 26,
        'legend.fontsize': 16,
    })

    fig, ax = plt.subplots(figsize=(6.5, 5), dpi=300)

    # Plot with mean line and std band
    lines = []
    colors = {
        'Day 1': '#1f77b4',
        'Day 3': '#2ca02c',
        'Day 7': '#d62728',
    }

    for label, mean, std in [
        ("Day 1", m1, s1),
        ("Day 3", m3, s3),
        ("Day 7", m7, s7),
    ]:
        # User requested adjustment to make error band visible. 
        # Increasing transparency of the fill (alpha 0.18 -> 0.5)
        l, = ax.plot(x, mean, label=label, color=colors[label], linewidth=2)
        ax.fill_between(x, (mean - std), (mean + std), color=colors[label], alpha=0.5, linewidth=0)
        # Add explicit error bars for clarity (±1 std)
        ax.errorbar(
            x,
            mean,
            yerr=std,
            fmt='none',
            ecolor=colors[label],
            elinewidth=1.2,
            capsize=2,
            alpha=0.9,
            zorder=2,
        )
        lines.append(l)

    ax.set_xlabel("Temperature (°C)", fontsize=26, fontweight='bold')
    ax.set_ylabel("Fluorescence (a.u.)", fontsize=26, fontweight='bold')
    
    ax.set_xlim(15, 47)
    style_axes(ax)
    ax.legend(loc='best', frameon=False)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(here, "THT_aging.csv")
    out_path = os.path.join(here, "output", "THT_aging.png")
    plot_aging(csv_path, out_path)
