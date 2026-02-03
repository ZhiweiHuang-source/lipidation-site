import os
import csv
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.ticker import ScalarFormatter, MultipleLocator
from typing import List, Dict, Optional

# Settings
FILE_PATH = 'THT.csv'
OUTPUT_DIR = 'output'
SUMMARY_FILE = 'max_y_summary.csv'

# Plotting Settings
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
    """Ensure output directories exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def normalize_header(value: str) -> str:
    """Clean header names to preserve multi-word labels."""
    s = str(value)
    for ch in ('\u00a0', '\xa0', '\ufffd'):
        s = s.replace(ch, ' ')
    s = re.sub(r'\s+', ' ', s).strip().strip('"\'')
    # Keep alphanumeric, underscore, space, hyphen
    s = re.sub(r'[^0-9A-Za-z_ \-]+', '', s)
    return s

def get_formatted_title(sample_name: str) -> str:
    """Generate a formatted title using subscript notation."""
    if re.fullmatch(r"[A-Za-z]{3}", sample_name):
        return f"m-[{sample_name}]-V$_30$" # using math mode for subscript
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
    """Create and save the plot for a single sample."""
    
    # Configure Matplotlib fonts
    mpl.rcParams['mathtext.fontset'] = 'dejavusans'
    mpl.rcParams['mathtext.default'] = 'regular'

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    
    # Plot data
    ax.plot(temperature, mean_data, color=COLOR_MEAN, linewidth=LINE_WIDTH)
    ax.fill_between(temperature, mean_data - std_data, mean_data + std_data, 
                    color=COLOR_STD, alpha=0.5)

    # Styling
    ax.set_xlabel('Temperature(°C)', fontsize=FONT_SIZE_AXIS, weight='bold')
    ax.set_ylabel('Fluorescence (a.u.)', fontsize=FONT_SIZE_AXIS, weight='bold')
    
    title_text = get_formatted_title(sample_name)
    ax.set_title(title_text, fontsize=FONT_SIZE_TITLE, weight='bold', pad=20)
    
    ax.set_ylim(Y_LIMITS)
    ax.set_xlim(X_LIMITS)
    
    # Ticks and Grid
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_major_locator(MultipleLocator(500000))
    ax.yaxis.set_major_formatter(ScalarFormatter(useMathText=True))
    ax.tick_params(axis='both', which='major', width=5, length=10, labelsize=FONT_SIZE_TICK)
    
    # Offset text size (scientific notation)
    ax.yaxis.get_offset_text().set_fontsize(16)
    ax.yaxis.get_offset_text().set_fontweight('bold')

    # Spines
    for spine in ax.spines.values():
        spine.set_linewidth(5)
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # Max value line
    ax.axhline(y=max_y, color='gray', linestyle='--', linewidth=5, zorder=10)

    # Box aspect
    ax.set_box_aspect(1.5 / 1.8)

    # Layout
    plt.subplots_adjust(left=0.23, right=0.95, top=0.82, bottom=0.23) # Fixed padding

    # Save
    out_path = os.path.join(OUTPUT_DIR, f'{sample_name}.png')
    plt.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path

def main():
    if not os.path.exists(FILE_PATH):
        print(f"Error: {FILE_PATH} not found.")
        return

    setup_files()
    
    # Read Data
    # Use latin1 as per original script
    try:
        df = pd.read_csv(FILE_PATH, encoding='latin1')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Extract Temperature (Col 0)
    # Assumes data starts at row 1 (0-indexed header) 
    # and we take 1024 rows like originals script (though simply taking all valid rows is safer)
    # Original logic: df.iloc[1:1+1024] -> skipping the first data row? No, 1:1025.
    # Note: df.iloc[1:] usually skips the first row of the DATAFRAME.
    # IF read_csv parsed header, Row 0 is the first data row.
    # The original script did `df.iloc[1:1+1024]`. This implies Row 0 was maybe a unit row or garbage?
    # I will stick to dynamic length but skip the first row if it looks non-numeric.
    
    # Let's clean the dataframe first to pure numeric
    # Assuming first column is temperature
    
    # Check if row 0 is numeric.
    try:
        float(df.iloc[0, 0])
        start_idx = 0
    except ValueError:
        start_idx = 1 # Skip unit row if present

    numeric_df = df.iloc[start_idx:].copy()
    
    # Limit to 1024 rows if strictly required, otherwise assume all data is good
    if len(numeric_df) > 1024:
        numeric_df = numeric_df.iloc[:1024]

    try:
        temperature = numeric_df.iloc[:, 0].astype(float).values
    except Exception as e:
        print(f"Error parsing temperature column: {e}")
        return

    name_map = {
        "SAA_redo_new": "SAA",
        "SAA_redo_new protein": "SAA",
        "SAA redo new protein": "SAA",
        "ELP": "V30",
        "mELP": "m-V30",
        "mV30": "m-V30"
    }

    summary_csv_path = os.path.join(OUTPUT_DIR, SUMMARY_FILE)
    
    with open(summary_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Sample', 'Max_Y', 'Std_At_MaxY'])

        columns = list(df.columns)
        
        # Iterate over triplets (Temp is Col 0, so samples start at Col 1)
        for col_start in range(1, len(columns), 3):
            if col_start + 2 >= len(columns):
                break

            header = normalize_header(columns[col_start])
            if header.startswith('Unnamed'):
                continue
            
            sample_name = name_map.get(header, header)
            print(f"Processing {sample_name}...")

            try:
                # Extract repeats
                repeats = []
                for i in range(3):
                    col_idx = col_start + i
                    data = numeric_df.iloc[:, col_idx].astype(float).values
                    repeats.append(data)
                
                repeats = np.array(repeats)
                
                # Statistics
                mean_val = np.nanmean(repeats, axis=0)
                std_val = np.nanstd(repeats, axis=0)
                
                idx_max = np.nanargmax(mean_val)
                max_y = mean_val[idx_max]
                std_at_max = std_val[idx_max]

                # Plot
                out_img = plot_sample(temperature, mean_val, std_val, sample_name, max_y)
                print(f"  Saved plot: {out_img}")
                
                # Save Summary
                writer.writerow([sample_name, max_y, std_at_max])

            except Exception as e:
                print(f"  Error processing {sample_name}: {e}")

    print(f"Done. Summary saved to {summary_csv_path}")

if __name__ == "__main__":
    main()
