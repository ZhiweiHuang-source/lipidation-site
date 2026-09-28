inDir  = getDirectory("Choose the folder containing the .czi images");
outDir = getDirectory("Choose an output folder");

list = getFileList(inDir);
czi = newArray(0);
for (i = 0; i < list.length; i++) {
    if (endsWith(toLowerCase(list[i]), ".czi")) czi = Array.concat(czi, list[i]);
}
if (czi.length == 0) exit("No .czi files found in:\n" + inDir);

run("Set Measurements...",
    "area centroid perimeter shape fit feret's display redirect=None decimal=4");
setOption("ExpandableArrays", true);

for (f = 0; f < czi.length; f++) {
    path = inDir + czi[f];
    cond = conditionFromName(czi[f]);

    run("Close All");
    roiManager("reset");
    run("Clear Results");
    run("Bio-Formats Importer",
        "open=[" + path + "] autoscale color_mode=Default " +
        "view=Hyperstack stack_order=XYCZT");
    getPixelSize(unit, pw, ph);
    if (unit == "pixel" || pw == 1)
        showMessage("No spatial calibration",
            "No pixel size was read from " + czi[f] + ".\n" +
            "Set it via Image > Properties before continuing.");

    run("Enhance Contrast", "saturated=0.35");
    setTool("freehand");
    roiManager("Show All without labels");

    waitForUser(cond + "  -  round 1 of 2: ISOLATED condensates",
        "Trace every condensate that touches nothing.\n" +
        "Draw an outline, press t to add it, repeat.\n" +
        "Work systematically across the field.\n" +
        "Click OK when done.");
    nIsolated = roiManager("count");

    waitForUser(cond + "  -  round 2 of 2: TOUCHING condensates",
        "Trace condensates that touch a neighbour, only where the\n" +
        "boundary between them can be followed. Skip anything that\n" +
        "may be two condensates fusing.\n" +
        "Click OK when done.");
    nTotal = roiManager("count");
    if (nTotal == 0) continue;

    run("Clear Results");
    roiManager("Deselect");
    roiManager("Measure");
    for (i = 0; i < nResults; i++) {
        setResult("Condition", i, cond);
        setResult("SourceFile", i, czi[f]);
        setResult("ObjectID", i, i + 1);
        if (i < nIsolated) setResult("Contact", i, 0);
        else               setResult("Contact", i, 1);
        a = getResult("Area", i);
        setResult("EquivDiam", i, 2 * sqrt(a / PI));
    }
    updateResults();
    saveAs("Results", outDir + cond + "_manual.csv");
    roiManager("Deselect");
    roiManager("Save", outDir + cond + "_rois.zip");
    print(cond + ": " + nTotal + " condensates (" + nIsolated + " isolated)");
}
run("Close All");

function conditionFromName(name) {
    known = newArray("mAGA", "mLSL", "mASG");
    for (i = 0; i < known.length; i++) {
        if (indexOf(name, known[i]) >= 0) return known[i];
    }
    stem = replace(name, "\\.czi$", "");
    parts = split(stem, "_");
    if (parts.length > 1) return parts[1];
    return stem;
}
