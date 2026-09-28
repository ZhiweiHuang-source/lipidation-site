import os
import csv
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.ticker import ScalarFormatter, MultipleLocator
from typing import List, Dict, Optional

FILE_PATH = 'THT.csv'
OUTPUT_DIR = 'output'
SUMMARY_FILE = 'max_y_summary.csv'

FIG_SIZE = (6.5, 5)
LINE_WIDTH = 5
FONT_SIZE_AXIS = 26
FONT_SIZE_TITLE = 30
FONT_SIZE_TICK = 26
Y_LIMITS = (-100000, 2200000)
X_LIMITS = (14.5, 51)
COLOR_MEAN = 'green'
COLOR_STD = '#90ee90'

def setup_files():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def normalize_header(value: str) -> str:
    s = str(value)
    for ch in ('\u00a0', '\xa0', '\ufffd'):
        s = s.replace(ch, ' ')
    s = re.sub(r'\s+', ' ', s).strip().strip('"\'')
    s = re.sub(r'[^0-9A-Za-z_ \-]+', '', s)
    return s

def get_formatted_title(sample_name: str) -> str:
    if re.fullmatch(r"[A-Za-z]{3}", sample_name):
        return f"m-[{sample_name}]-V$_30$"
    elif sample_name == "V30":
        return "V$_30$"
    elif sample_name == "m-V30":
        return "m-V$_30$"
    elif sample_name.startswith("Unlipidated"):
        match = re.search(r"Unlipidated\s+([A-Za-z0-9]+)", sample_name)
        if match:
            return f"[{match.group(1)}]-V$_30$"
    return sample_name

def plot_sample(temperature: np.ndarray,
                mean_data: np.ndarray,
                std_data: np.ndarray,
                sample_name: str,
                max_y: float) -> str:

    mpl.rcParams['mathtext.fontset'] = 'dejavusans'
    mpl.rcParams['mathtext.default'] = 'regular'

    fig, ax = plt.subplots(figsize=FIG_SIZE)

    ax.plot(temperature, mean_data, color=COLOR_MEAN, linewidth=LINE_WIDTH)
    ax.fill_between(temperature, mean_data - std_data, mean_data + std_data,
                    color=COLOR_STD, alpha=0.5)

    ax.set_xlabel('Temperature(°C)', fontsize=FONT_SIZE_AXIS, weight='bold')
    ax.set_ylabel('Fluorescence (a.u.)', fontsize=FONT_SIZE_AXIS, weight='bold')

    title_text = get_formatted_title(sample_name)
    ax.set_title(title_text, fontsize=FONT_SIZE_TITLE, weight='bold', pad=20)

    ax.set_ylim(Y_LIMITS)
    ax.set_xlim(X_LIMITS)

    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_major_locator(MultipleLocator(500000))
    ax.yaxis.set_major_formatter(ScalarFormatter(useMathText=True))
    ax.tick_params(axis='both', which='major', width=5, length=10, labelsize=FONT_SIZE_TICK)

    ax.yaxis.get_offset_text().set_fontsize(16)
    ax.yaxis.get_offset_text().set_fontweight('bold')

    for spine in ax.spines.values():
        spine.set_linewidth(5)
    ax.grid(True, linestyle='--', alpha=0.3)

    ax.axhline(y=max_y, color='gray', linestyle='--', linewidth=5, zorder=10)

    ax.set_box_aspect(1.5 / 1.8)

    plt.subplots_adjust(left=0.23, right=0.95, top=0.82, bottom=0.23)

    out_path = os.path.join(OUTPUT_DIR, f'{sample_name}.png')
    plt.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path

def main():
    if not os.path.exists(FILE_PATH):
        print(f"Error: {FILE_PATH} not found.")
        return

    setup_files()

    try:
        df = pd.read_csv(FILE_PATH, encoding='latin1')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    try:
        float(df.iloc[0, 0])
        start_idx = 0
    except ValueError:
        start_idx = 1

    numeric_df = df.iloc[start_idx:].copy()

    if len(numeric_df) > 1024:
        numeric_df = numeric_df.iloc[:1024]

    try:
        temperature = numeric_df.iloc[:, 0].astype(float).values
    except Exception as e:
        print(f"Error parsing temperature column: {e}")
        return

    name_map = {
        "ELP": "V30",
        "mELP": "m-V30",
        "mV30": "m-V30"
    }

    summary_csv_path = os.path.join(OUTPUT_DIR, SUMMARY_FILE)

    with open(summary_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Sample', 'Max_Y', 'Std_At_MaxY'])

        columns = list(df.columns)

        for col_start in range(1, len(columns), 3):
            if col_start + 2 >= len(columns):
                break

            header = normalize_header(columns[col_start])
            if header.startswith('Unnamed'):
                continue

            sample_name = name_map.get(header, header)
            print(f"Processing {sample_name}...")

            try:
                repeats = []
                for i in range(3):
                    col_idx = col_start + i
                    data = numeric_df.iloc[:, col_idx].astype(float).values
                    repeats.append(data)

                repeats = np.array(repeats)

                mean_val = np.nanmean(repeats, axis=0)
                std_val = np.nanstd(repeats, axis=0)

                idx_max = np.nanargmax(mean_val)
                max_y = mean_val[idx_max]
                std_at_max = std_val[idx_max]

                out_img = plot_sample(temperature, mean_val, std_val, sample_name, max_y)
                print(f"  Saved plot: {out_img}")

                writer.writerow([sample_name, max_y, std_at_max])

            except Exception as e:
                print(f"  Error processing {sample_name}: {e}")

    print(f"Done. Summary saved to {summary_csv_path}")

if __name__ == "__main__":
    main()
