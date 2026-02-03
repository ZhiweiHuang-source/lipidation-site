---
layout: home
title: K partition (Fiji macro)
---

# K partition (Fiji macro)

Compute partition coefficients (K1/K2) from two-channel OME-TIFFs using a single Fiji macro. Robust masks, multiple dilute-region modes, optional background subtraction, and QA outputs.

- Macro: [compute_k12_unified.ijm](./compute_k12_unified.ijm)
- Usage and details: [README](./README.md)
- License: MIT

Quick start:
1) In Fiji, open the macro file and run “Unified: Build/Use Masks + Compute K1/K2”.
2) Pick your image directory and mask output directory.
3) Adjust options as needed (threshold method, polarity, dilute region, ring width).
4) Results CSV and mask PNGs are saved in the chosen mask directory.

If you publish this workflow, please cite the repository and your paper.
