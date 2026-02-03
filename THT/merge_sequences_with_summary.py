import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
seq_path = BASE_DIR / 'my_sequences.csv'
sum_path = BASE_DIR / 'output' / 'max_y_summary.csv'
out_path = BASE_DIR / 'my_sequences_with_summary.csv'

# Read sequences, only first 4 columns to ignore trailing empty columns in file
seq_df = pd.read_csv(seq_path, usecols=[0, 1, 2, 3])
# Build join key matching 'Sample' in summary
seq_df['Sample'] = seq_df['P2'].astype(str) + seq_df['P3'].astype(str) + seq_df['P4'].astype(str)

# Replace numeric class codes with labels
_class_map = {1: 'droplet', 2: 'metastable', 3: 'fiber'}
# Coerce to numeric first in case they are strings, then map to labels
seq_df['class'] = pd.to_numeric(seq_df['class'], errors='coerce').map(_class_map)

# Read summary
sum_df = pd.read_csv(sum_path)

# Merge: left join to keep all entries from my_sequences
merged = seq_df.merge(sum_df, how='left', on='Sample')

# Optional: sort by Sample for readability
merged = merged[['P2', 'P3', 'P4', 'class', 'Sample', 'Max_Y', 'Std_At_MaxY']]
merged.sort_values(['P2', 'P3', 'P4'], inplace=True, ignore_index=True)

# Write output
merged.to_csv(out_path, index=False)

print(f'Wrote merged CSV to: {out_path}')
