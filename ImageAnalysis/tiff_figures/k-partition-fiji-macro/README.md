# Fiji macro for partition coefficient (K) analysis

This repository contains the Fiji/ImageJ macro used to compute partition coefficients (K1/K2) from two-channel OME-TIFF images of phase-separated droplets.

## What it does
- Opens OME-TIFFs with Bio-Formats.
- Builds binary masks for IDP1 and IDP2 using Otsu thresholding and optional morphology/unify steps.
- Defines dilute regions (default: other IDP mask) via binary image math.
- Measures mean intensities with robust mask multiplication (no ROI artifacts).
- Computes K1/K2 as dense/dilute means.
- Saves CSV results and QA mask images/overlays.

## Files
- `compute_k12_unified.ijm`: unified macro to run end-to-end (present version from the paper).
- `example/`: optional sample structure to place a few example images (not provided here).

## Usage
1. Open Fiji and run Plugins > Macros > Run... and choose `compute_k12_unified.ijm`.
2. Choose your image directory (OME-TIFFs) and a mask output directory.
3. In the dialog, set channels and choose thresholding/morphology options as needed.
4. Press OK. A CSV is written to the masks folder when processing finishes; QA PNGs are saved per image.

## Reproducibility notes
- Threshold method default is Otsu; objects bright. Z-projection default is None.
- Dilute region default is “Other IDP mask.”
- Background subtraction is off by default.

## Citation
Please cite the paper associated with this macro. A citation stub will be added after acceptance.

## License
MIT (see LICENSE).
