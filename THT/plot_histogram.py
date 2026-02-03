import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

SUMMARY_PATH = os.path.join('output', 'max_y_summary.csv')
OUTPUT_IMG = os.path.join('output', 'max_y_histogram.png')
OUTPUT_IMG_ALT = os.path.join('output', 'max_y_histograme.png')
OUTPUT_SORTED_CSV = os.path.join('output', 'max_y_summary_sorted.csv')


def main():
    if not os.path.exists(SUMMARY_PATH):
        raise FileNotFoundError(f"Summary CSV not found: {SUMMARY_PATH}. Run plot_GGG.py first.")

    df = pd.read_csv(SUMMARY_PATH)
    if 'Sample' not in df.columns or 'Max_Y' not in df.columns:
        raise ValueError("Expected columns 'Sample' and 'Max_Y' in summary CSV.")

    # Optional error bar column
    has_std = 'Std_At_MaxY' in df.columns

    # Sort by Max_Y descending (for CSV); we'll reorder for plotting below
    df_sorted = df.sort_values(by='Max_Y', ascending=False, ignore_index=True)

    # For plotting: move special controls to the far right, keeping their internal order
    # Include unlipidated groups as requested
    special = {"V30", "m-V30", "PBS", "Unlipidated ASL", "Unlipidated LGA"}
    df_main = df_sorted[~df_sorted['Sample'].isin(special)]
    df_special = df_sorted[df_sorted['Sample'].isin(special)]
    df_plot = pd.concat([df_main, df_special], ignore_index=True)

    # Save a sorted copy for convenience (strictly sorted desc)
    df_sorted.to_csv(OUTPUT_SORTED_CSV, index=False)

    # Plot bar chart
    plt.figure(figsize=(22, 9))  # larger for readability
    y = df_plot['Max_Y'].values
    x = range(len(df_plot))
    yerr = df_plot['Std_At_MaxY'].values if has_std else None

    # Highlight selected samples
    highlight = {"GGG", "GAG", "LAA", "LSL", "ALS", "SLS",
                 "LGL_trail2", "GAG_trail2", "ALS_trail2",
                 "Unlipidated ASL", "Unlipidated LGA", "V30", "m-V30"}
    samples = df_plot['Sample'].tolist()
    colors = ["orange" if s in highlight else "forestgreen" for s in samples]

    bars = plt.bar(x, y, yerr=yerr, capsize=3.5, color=colors, edgecolor='black', linewidth=0.8)
    # Thicker outline for highlighted bars
    for bar, s in zip(bars, samples):
        if s in highlight:
            bar.set_linewidth(2.0)

    plt.xticks(range(len(df_plot)), df_plot['Sample'], rotation=90, fontsize=26, weight='bold')
    plt.ylabel('Max Fluorescence (a.u.)', fontsize=26, weight='bold')
    # No x-axis label per request
    plt.title('Max Fluorescence by Sample (sorted high→low)', fontsize=30, weight='bold', pad=20)

    ax = plt.gca()
    ax.yaxis.set_major_formatter(ScalarFormatter(useMathText=True))
    plt.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
    # Increase y tick label size for visibility
    plt.yticks(fontsize=26, weight='bold')

    # make the major tick thickness larger (width=5)
    ax.tick_params(axis='y', which='major', width=5, length=10)

    # Add light grid for readability
    plt.grid(axis='y', linestyle='--', alpha=0.3)

    # Thicken border like prior plots
    for spine in ax.spines.values():
        spine.set_linewidth(5)

    plt.tight_layout()
    plt.savefig(OUTPUT_IMG, dpi=240)
    # Also save an alternate name upon request
    plt.savefig(OUTPUT_IMG_ALT, dpi=240)
    plt.close()
    print(f"Histogram saved as {OUTPUT_IMG}")
    print(f"Sorted summary saved as {OUTPUT_SORTED_CSV}")


if __name__ == '__main__':
    main()
