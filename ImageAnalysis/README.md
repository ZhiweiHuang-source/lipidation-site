# Image Analysis

This folder contains scripts and Fiji macros for confocal image analysis, specifically for computing partition coefficients.

## Contents

### Partition Coefficient Analysis (`tiff_figures/`)

Scripts for analyzing protein droplet formation and calculating partition coefficients ($K_p = \text{Mean}_{\text{dense}} / \text{Mean}_{\text{dilute}}$).

- **`compute_k12_unified.ijm`**: A Fiji (ImageJ) macro that automates mask generation and intensity measurement from OME-TIFF images. It identifies protein droplets and background regions to calculate intensities.
- **`compute_partition_coefficients.py`**: A Python script to calculate partition coefficients from OME-TIFF images utilizing binary masks (PNGs).
- **`generate_masks_and_summary.py`**: Helper script to generate masks and summary statistics.
- **`make_mask_panels.py`**: Generates visual panels showing the images and their corresponding masks for quality control.

## Usage

### Fiji Macro
1. Open Fiji (ImageJ).
2. Run `Plugins > Macros > Run...` and select `compute_k12_unified.ijm`.
3. Select your input image directory and mask directory when prompted.

### Python Analysis
To run the python analysis on the example data:

```bash
python tiff_figures/compute_partition_coefficients.py --channel 0 --dilute global
```

## Data Availability
Due to file size limitations, raw `.ome.tif` confocal images are not included in this repository. 
A `clean_and_audit.py` script is provided to audit the dataset structure.
