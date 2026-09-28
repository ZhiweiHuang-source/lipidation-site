import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

SUMMARY_PATH = os.path.join('output', 'max_y_summary.csv')
OUTPUT_IMG = os.path.join('output', 'max_y_histogram.png')
OUTPUT_SORTED_CSV = os.path.join('output', 'max_y_summary_sorted.csv')

def main():
    if not os.path.exists(SUMMARY_PATH):
        raise FileNotFoundError(f"Summary CSV not found: {SUMMARY_PATH}. Run plot_GGG.py first.")

    df = pd.read_csv(SUMMARY_PATH)
    if 'Sample' not in df.columns or 'Max_Y' not in df.columns:
        raise ValueError("Expected columns 'Sample' and 'Max_Y' in summary CSV.")

    has_std = 'Std_At_MaxY' in df.columns

    df_sorted = df.sort_values(by='Max_Y', ascending=False, ignore_index=True)

    special = {"V30", "m-V30", "PBS", "Unlipidated ASL", "Unlipidated LGA"}
    df_main = df_sorted[~df_sorted['Sample'].isin(special)]
    df_special = df_sorted[df_sorted['Sample'].isin(special)]
    df_plot = pd.concat([df_main, df_special], ignore_index=True)

    df_sorted.to_csv(OUTPUT_SORTED_CSV, index=False)

    plt.figure(figsize=(22, 9))
    y = df_plot['Max_Y'].values
    x = range(len(df_plot))
    yerr = df_plot['Std_At_MaxY'].values if has_std else None

    plt.bar(x, y, yerr=yerr, capsize=3.5, color="forestgreen", edgecolor='black', linewidth=0.8)

    plt.xticks(range(len(df_plot)), df_plot['Sample'], rotation=90, fontsize=26, weight='bold')
    plt.ylabel('Max Fluorescence (a.u.)', fontsize=26, weight='bold')

    ax = plt.gca()
    ax.yaxis.set_major_formatter(ScalarFormatter(useMathText=True))
    plt.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
    plt.yticks(fontsize=26, weight='bold')

    ax.tick_params(axis='y', which='major', width=5, length=10)

    plt.grid(axis='y', linestyle='--', alpha=0.3)

    for spine in ax.spines.values():
        spine.set_linewidth(5)

    plt.tight_layout()
    plt.savefig(OUTPUT_IMG, dpi=240)
    plt.close()
    print(f"Histogram saved as {OUTPUT_IMG}")
    print(f"Sorted summary saved as {OUTPUT_SORTED_CSV}")

if __name__ == '__main__':
    main()
