# ImageJ/Fiji Macros Directory

This directory contains ImageJ/Fiji macros for analyzing microscopy images related to lipidation site research.

## Common Applications

### Image Analysis Tasks
- Quantify fluorescence intensity at membrane vs cytoplasm
- Measure colocalization of lipidated proteins
- Track protein localization changes
- Batch process multiple images

## Macro Template

Example macro structure:

```javascript
// Macro Name: analyze_fluorescence.ijm
// Description: Measure fluorescence intensity in different cellular compartments
// Author: [Your Name]
// Date: [Date]

// Get the title of the active image
title = getTitle();

// Set measurements
run("Set Measurements...", "area mean min integrated redirect=None decimal=3");

// Your analysis code here
// Example: Select ROI and measure
//setTool("polygon");
//waitForUser("Select membrane region and click OK");
//run("Measure");

print("Analysis complete for: " + title);
```

## Usage

1. Open ImageJ/Fiji
2. Load your image
3. Go to Plugins > Macros > Run
4. Select the appropriate macro from this directory
5. Follow any on-screen instructions

Place your custom ImageJ macros (*.ijm files) in this directory.
