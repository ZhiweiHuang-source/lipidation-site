# lipidation-site

Analysis code for Huang *et al.*, "Lipoengineering of Biomolecular Condensates Controls Material Properties and Multiphase Hierarchy to Guide Organoid Morphogenesis".

Methods are described in the manuscript and Supplementary Information. Input data files are not included in this repository.

Python scripts take their input files as arguments, or open a file picker when run without arguments:

```bash
python hplc/plot_hplc.py data1.csv data2.csv
python maldi/plot_maldi.py theoretical_masses.csv spectra1.csv spectra2.csv
```

## Requirements

Python 3.12 and Fiji (ImageJ 1.54p).

```bash
pip install -r requirements.txt
```

## Contents

| Folder | File | Output | Figure |
|---|---|---|---|
| `hplc/` | `plot_hplc.py` | RP-HPLC chromatograms and retention times | Fig. 2c; Supplementary Figs. 3–6 |
| `maldi/` | `plot_maldi.py` | MALDI-TOF spectra; observed and theoretical masses | Supplementary Figs. 7–12; Supplementary Table 3 |
| `tht/` | `plot_tht_curves.py` | ThT fluorescence curves and maxima | Supplementary Fig. 22 |
| `tht/` | `plot_tht_max.py` | Maximum ThT fluorescence | Fig. 3c |
| `tht/` | `plot_tht_aging.py` | ThT fluorescence during maturation | Fig. 3d |
| `partition/` | `partition_coefficients.ijm` | Partition coefficients | Supplementary Fig. 48a |
| `condensates/` | `count_foci_per_cell.ijm` | Intracellular foci per cell length | Fig. 7b |
| `condensates/` | `trace_condensates.ijm`, `condensate_shape.py` | Condensate size and anisotropy | Fig. 7k |
| `organoids/` | `merge_z_pairs.py` | Detections merged across focal planes | Fig. 8e–g |
| `organoids/` | `score_budding.ijm` | Budding scores | Fig. 8e; Supplementary Fig. 69c |
| `organoids/` | `analyse_batches.py` | Colony-formation efficiency, budding organoids, composition | Fig. 8e–g; Supplementary Fig. 65 |
| `organoids/` | `depth_coded_projection.py` | Depth-coded projections | Fig. 8i–k; Supplementary Figs. 64, 69e |
| `organoids/` | `organoid_brightfield.ijm` | Representative brightfield images | Supplementary Fig. 69d |

## Licence

MIT (see `LICENSE`). For questions, contact the corresponding author.
