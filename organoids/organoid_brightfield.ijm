var MAKE_ZOOM = false;
var scaleDistance = 600;
var scaleKnown = 530;
var dispMin = 20;
var autoSaturation = 0.35;
var scaleBarUM = 500;
var barThickness = 40;
var barFont = 200;
var zoomUM = 500;
var detailBarUM = 100;
var detailBarThickness = 8;
var detailBarFont = 40;
var boxColor = "yellow";
var boxLineWidth = 12;
var fileTypes = "tif,tiff,png,jpg,jpeg";

inputDir  = getDirectory("Choose the folder containing your organoid images");
outputDir = inputDir + "Processed_Images" + File.separator;
File.makeDirectory(outputDir);
types = split(fileTypes, ",");
list  = getFileList(inputDir);
if (MAKE_ZOOM) barOpt = " bold hide overlay";
else           barOpt = " bold overlay";
if (!MAKE_ZOOM) setBatchMode(true);

for (i = 0; i < list.length; i++) {
    ok = false;
    for (t = 0; t < types.length; t++)
        if (endsWith(toLowerCase(list[i]), "." + types[t])) ok = true;
    if (!ok) continue;
    base = substring(list[i], 0, lastIndexOf(list[i], "."));

    open(inputDir + list[i]);
    run("8-bit");
    run("Set Scale...", "distance=" + scaleDistance + " known=" + scaleKnown +
        " pixel=1 unit=um");
    side = minOf(getWidth(), getHeight());
    makeRectangle(round((getWidth() - side) / 2), round((getHeight() - side) / 2), side, side);
    run("Crop");
    rename("sq");
    run("Enhance Contrast", "saturated=" + autoSaturation);
    getMinAndMax(lo, hi);
    setMinAndMax(dispMin, hi);
    makeOval(0, 0, getWidth(), getHeight());
    run("Make Inverse");
    setBackgroundColor(0, 0, 0);
    run("Clear", "slice");
    run("Select None");

    if (!MAKE_ZOOM) {
        run("Scale Bar...", "width=" + scaleBarUM + " height=" + barThickness +
            " thickness=" + barThickness + " font=" + barFont +
            " color=White background=None location=[Lower Right]" + barOpt);
        run("Flatten");
        saveAs("PNG", outputDir + base + "_processed.png");
        run("Close All");
        continue;
    }

    getPixelSize(u, pw, ph);
    zoomPx = round(zoomUM / pw);
    if (zoomPx > getWidth())  zoomPx = getWidth();
    if (zoomPx > getHeight()) zoomPx = getHeight();
    cx = round(getWidth() / 2 - zoomPx / 2);
    cy = round(getHeight() / 2 - zoomPx / 2);
    makeRectangle(cx, cy, zoomPx, zoomPx);
    waitForUser("Select zoom region",
        list[i] + "\n \nMove the " + zoomUM + " um box over the region to enlarge,\n" +
        "then click OK.");
    if (selectionType() == -1) { zx = cx; zy = cy; }
    else { getSelectionBounds(zx, zy, zw, zh); }
    if (zx < 0) zx = 0;
    if (zy < 0) zy = 0;
    if (zx + zoomPx > getWidth())  zx = getWidth()  - zoomPx;
    if (zy + zoomPx > getHeight()) zy = getHeight() - zoomPx;
    selectWindow("sq");
    run("Select None");

    run("Duplicate...", "title=full"); selectWindow("full");
    setMinAndMax(dispMin, hi);
    run("Scale Bar...", "width=" + scaleBarUM + " height=" + barThickness +
        " thickness=" + barThickness + " font=" + barFont +
        " color=White background=None location=[Lower Right]" + barOpt);
    run("Flatten");
    saveAs("PNG", outputDir + base + "_processed.png");
    close();
    if (isOpen("full")) { selectWindow("full"); close(); }

    selectWindow("sq"); run("Duplicate...", "title=box"); selectWindow("box");
    setMinAndMax(dispMin, hi);
    run("Scale Bar...", "width=" + scaleBarUM + " height=" + barThickness +
        " thickness=" + barThickness + " font=" + barFont +
        " color=White background=None location=[Lower Right]" + barOpt);
    makeRectangle(zx, zy, zoomPx, zoomPx);
    Overlay.addSelection(boxColor, boxLineWidth);
    run("Select None");
    run("Flatten");
    saveAs("PNG", outputDir + base + "_highlight.png");
    close();
    if (isOpen("box")) { selectWindow("box"); close(); }

    selectWindow("sq");
    makeRectangle(zx, zy, zoomPx, zoomPx);
    run("Duplicate...", "title=zoom"); selectWindow("zoom");
    setMinAndMax(dispMin, hi);
    run("Scale Bar...", "width=" + detailBarUM + " height=" + detailBarThickness +
        " thickness=" + detailBarThickness + " font=" + detailBarFont +
        " color=Black background=None location=[Lower Right]" + barOpt);
    run("Flatten");
    saveAs("PNG", outputDir + base + "_zoom.png");
    run("Close All");
}
if (!MAKE_ZOOM) setBatchMode(false);
print("Done: " + outputDir);
