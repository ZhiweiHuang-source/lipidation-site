// ImageJ Macro: measure_membrane_fluorescence.ijm
// Description: Measure fluorescence intensity at membrane and cytoplasm regions
// Author: [Your Name]
// Date: [Date]
//
// This macro helps quantify the distribution of fluorescent signal
// between membrane and cytoplasmic regions, useful for studying
// protein localization after lipidation.

// Usage:
// 1. Open your fluorescence image in ImageJ
// 2. Run this macro (Plugins > Macros > Run)
// 3. Draw ROI around membrane region when prompted
// 4. Draw ROI around cytoplasmic region when prompted
// 5. Results will be displayed in the Results window

// Get the title of the active image
if (nImages == 0) {
    showMessage("Error", "No image is open. Please open an image first.");
    exit();
}

title = getTitle();
print("\\Clear"); // Clear the log window
print("=== Membrane Fluorescence Analysis ===");
print("Image: " + title);
print("");

// Set measurements to include area, mean intensity, and integrated density
run("Set Measurements...", "area mean integrated min max redirect=None decimal=3");

// Clear any existing results
run("Clear Results");

// Step 1: Measure background
setTool("rectangle");
waitForUser("Background Selection", "Draw a small ROI in a background region (no cells)\nand click OK");
run("Measure");
bg_mean = getResult("Mean", 0);
print("Background mean intensity: " + bg_mean);

// Step 2: Measure membrane region
setTool("polygon");
waitForUser("Membrane Selection", "Draw an ROI around the membrane region\nand click OK");
run("Measure");
membrane_mean = getResult("Mean", 1);
membrane_area = getResult("Area", 1);
membrane_intden = getResult("IntDen", 1);
membrane_corrected = membrane_mean - bg_mean;
print("Membrane mean intensity: " + membrane_mean);
print("Membrane corrected intensity: " + membrane_corrected);
print("Membrane area: " + membrane_area);

// Step 3: Measure cytoplasm region
setTool("polygon");
waitForUser("Cytoplasm Selection", "Draw an ROI around the cytoplasmic region\n(avoiding nucleus if visible) and click OK");
run("Measure");
cyto_mean = getResult("Mean", 2);
cyto_area = getResult("Area", 2);
cyto_intden = getResult("IntDen", 2);
cyto_corrected = cyto_mean - bg_mean;
print("Cytoplasm mean intensity: " + cyto_mean);
print("Cytoplasm corrected intensity: " + cyto_corrected);
print("Cytoplasm area: " + cyto_area);

// Calculate membrane to cytoplasm ratio
if (cyto_corrected > 0) {
    ratio = membrane_corrected / cyto_corrected;
    print("");
    print("=== Summary ===");
    print("Membrane/Cytoplasm ratio: " + ratio);
    
    if (ratio > 1.5) {
        print("Interpretation: Strong membrane localization");
    } else if (ratio > 1.0) {
        print("Interpretation: Moderate membrane enrichment");
    } else if (ratio > 0.5) {
        print("Interpretation: Similar membrane and cytoplasm distribution");
    } else {
        print("Interpretation: Cytoplasmic localization");
    }
} else {
    print("Warning: Cytoplasm intensity too low for ratio calculation");
}

print("");
print("Analysis complete!");
print("Results are displayed in the Results window.");
