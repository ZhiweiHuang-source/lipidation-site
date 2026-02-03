# THT plotting quick guide

This folder contains two scripts to generate plots from `THT.csv`.

## 1) Generate per-sample curves and summary CSV

- Produces one PNG per sample in `output/`
- Writes `output/max_y_summary.csv` for the histogram

Run:

```powershell
python plot_GGG.py
```

## 2) Generate the overall histogram

- Reads `output/max_y_summary.csv`
- Saves `output/max_y_histogram.png`
- Also writes `output/max_y_summary_sorted.csv`

Run:

```powershell
C:/Users/zhiwe/AppData/Local/Programs/Python/Python311/python.exe plot_histogram.py
```

## Notes
- Column names are normalized to preserve multi-word labels (e.g., "Unlipidated ASL" and "Unlipidated LGA").
- If you add new samples/columns to `THT.csv`, just re-run the two commands above.
- Outputs are written to the `output/` directory.
