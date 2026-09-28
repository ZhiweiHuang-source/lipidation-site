inputDir = getDirectory("Choose the folder containing your .czi files");
if (inputDir == "") exit("No folder chosen.");
while (endsWith(inputDir, "/") || endsWith(inputDir, "\\"))
    inputDir = substring(inputDir, 0, lengthOf(inputDir) - 1);
outDir = inputDir + File.separator + "manual_counts";

modes = newArray("median to median + k x SD (recommended)",
                 "median to the cell's 99th percentile");
Dialog.create("Manual foci counting");
Dialog.addCheckbox("Blind the filenames", true);
Dialog.addToSameRow();
Dialog.addCheckbox("Skip fields already finished", true);
Dialog.addChoice("Contrast per cell", modes, modes[0]);
Dialog.addNumber("k", 5);
Dialog.addToSameRow();
Dialog.addNumber("Zoom %", 600);
Dialog.addMessage("---- these only PRE-TICK an exclude box ----");
Dialog.addNumber("Too dim below mean above background", 6);
Dialog.addNumber("Width over (um)", 1.30);
Dialog.addToSameRow();
Dialog.addNumber("Length over (um)", 5.50);
Dialog.addCheckbox("Dense cells leave the denominator", true);
Dialog.show();
blind     = Dialog.getCheckbox();
resume    = Dialog.getCheckbox();
mode      = Dialog.getChoice();
kSD       = Dialog.getNumber();
cellZoom  = Dialog.getNumber();
dimFloor  = Dialog.getNumber();
maxW      = Dialog.getNumber();
maxL      = Dialog.getNumber();
denseExcl = Dialog.getCheckbox();

chFluo    = 1;
chTrans   = 2;
fociTolPx = 2;

winW = round(screenWidth * 0.60);
winH = screenHeight - 140;
if (winW < 500) winW = 500;
if (winH < 400) winH = 400;
dlgX = winW + 20;

File.makeDirectory(outDir);
if (!File.isDirectory(outDir)) exit("Could not create the output folder:\n" + outDir);
setOption("ExpandableArrays", true);
roiDir = outDir + File.separator + "rois";
File.makeDirectory(roiDir);
tmpDir = outDir + File.separator + "temp";
File.makeDirectory(tmpDir);

cellCsv = outDir + File.separator + "manual_cells.csv";
fociCsv = outDir + File.separator + "manual_foci.csv";
keyCsv  = outDir + File.separator + "blinding_key.csv";
doneCsv = outDir + File.separator + "fields_done.csv";
scrCell = tmpDir + File.separator + "_partial_cells.csv";
scrFoci = tmpDir + File.separator + "_partial_foci.csv";

cellHdr = "field_id,file,subfolder,px_um,unit,cell_index,outline_source," +
          "area_um2,length_um,width_um," +
          "bg_field,cell_mean,cell_median,cell_sd,cell_p99,cell_max," +
          "peak_over_dilute,disp_min,disp_max,contrast_mode," +
          "scoreable,excluded_by,flag_dim,flag_dense,flag_unsure," +
          "n_foci,n_clicks_rejected,foci_per_um";
fociHdr = "field_id,file,cell_index,focus_index,x_px,y_px,x_um,y_um";

if (File.exists(cellCsv)) {
    gotHdr = firstLineOf(cellCsv);
    if (gotHdr != cellHdr)
        exit("manual_cells.csv in this folder has different columns.");
}
if (!File.exists(cellCsv)) File.append(cellHdr, cellCsv);
if (!File.exists(fociCsv)) File.append(fociHdr, fociCsv);
if (!File.exists(doneCsv)) File.append("field_id,file,subfolder,n_cells_outlined", doneCsv);
if (blind && !File.exists(keyCsv)) File.append("field_id,file,subfolder", keyCsv);
if (File.exists(scrCell)) File.delete(scrCell);
if (File.exists(scrFoci)) File.delete(scrFoci);

done = "";
if (resume && File.exists(doneCsv)) done = File.openAsString(doneCsv);
paths = newArray(0);
paths = listCzi(inputDir, paths);
if (paths.length == 0) exit("No .czi files found under:\n" + inputDir);
if (blind) {
    for (i = paths.length - 1; i > 0; i--) {
        j = floor(random * (i + 1));
        t = paths[i]; paths[i] = paths[j]; paths[j] = t;
    }
}
todo = newArray(0);
nAlready = 0;
for (i = 0; i < paths.length; i++) {
    nm = File.getName(paths[i]);
    sub0 = toSlash(stripPrefix(File.getParent(paths[i]), inputDir));
    while (startsWith(sub0, "/")) sub0 = substring(sub0, 1);
    if (sub0 == "") sub0 = ".";
    keyStr = "," + nm + ",\"" + sub0 + "\"";
    if (resume && indexOf(done, keyStr) >= 0) { nAlready++; continue; }
    todo[todo.length] = paths[i];
}
paths = todo;
if (paths.length == 0) exit("All " + nAlready + " field(s) already finished.");
nThis = paths.length;

sessTag = "" + (floor(getTime() / 1000) % 100000);
singleChAsked = 0; singleChIsFluo = 0;
nCellsDone = 0; nFociDone = 0; nFieldsDone = 0;

for (f = 0; f < nThis; f++) {
    path  = paths[f];
    fname = File.getName(path);
    sub   = toSlash(stripPrefix(File.getParent(path), inputDir));
    while (startsWith(sub, "/")) sub = substring(sub, 1);
    if (sub == "") sub = ".";

    if (blind) fieldId = "field_" + sessTag + "_" + IJ.pad(f + 1, 3);
    else       fieldId = stripExt(fname);
    if (blind) File.append(fieldId + "," + fname + ",\"" + sub + "\"", keyCsv);
    if (File.exists(scrCell)) File.delete(scrCell);
    if (File.exists(scrFoci)) File.delete(scrFoci);

    close("*");
    roiManager("reset");
    run("Bio-Formats Importer", "open=[" + path + "] color_mode=Composite " +
        "view=Hyperstack stack_order=XYCZT");
    if (nImages == 0) continue;
    getPixelSize(unit, pw, ph);
    getDimensions(iw, ih, nch, nsl, nfr);
    rename(fieldId);
    if (nch < chFluo) exit("This file has no channel " + chFluo + ".");
    isStack = (nch > 1);

    if (nch == 1) {
        if (singleChAsked == 0) {
            oneChOpts = newArray("It is mCherry - score these files",
                                 "It is transmitted light - skip these files");
            Dialog.create("Single-channel file");
            Dialog.addMessage(fname + " has only one channel.");
            Dialog.addChoice("This single channel is", oneChOpts, oneChOpts[0]);
            Dialog.show();
            oneChPick = Dialog.getChoice();
            singleChIsFluo = (oneChPick == oneChOpts[0]);
            singleChAsked  = 1;
        }
        if (singleChIsFluo == 0) continue;
    }

    if (isStack) Stack.setChannel(chFluo);
    run("Select None");
    bg    = getValue("Median");
    fldHi = pctileHere(0.999);
    if (isStack && nch >= chTrans) {
        Stack.setChannel(chTrans); resetMinAndMax(); run("Grays");
    }
    if (isStack) Stack.setChannel(chFluo);
    setMinAndMax(bg, maxOf(fldHi, bg + 10));
    run("Red");
    if (isStack && nch >= chTrans) Stack.setDisplayMode("composite");

    roiManager("Show All with labels");
    setLocation(0, 0, winW, winH);
    run("Set... ", "zoom=75 x=" + round(iw / 2) + " y=" + round(ih / 2));
    setTool("freehand");
    waitForUser("Field " + (f + 1) + "/" + nThis + "   [" + fieldId + "]",
        "Draw an outline around each cell to score, press t after each.\n" +
        "Nothing added = skip this field.\n \nOK when done.");

    nCell = roiManager("count");
    if (nCell == 0) {
        File.append(fieldId + "," + fname + ",\"" + sub + "\",0", doneCsv);
        continue;
    }

    for (c = 0; c < nCell; c++) {
        selectWindow(fieldId);
        if (isStack) Stack.setChannel(chFluo);
        roiManager("select", c);
        if (selectionType == 10) continue;

        Roi.getBounds(rx, ry, rw, rh);
        cx = round(rx + rw / 2);
        cy = round(ry + rh / 2);
        List.setMeasurements;
        area   = List.getValue("Area");
        feret  = List.getValue("Feret");
        minfer = List.getValue("MinFeret");
        getStatistics(cA, cMean, cMin, cMax, cSd);
        cMed = getValue("Median");
        cP99 = pctileHere(0.99);

        meanAbove = cMean - bg;
        dilute    = maxOf(cMed - bg, 0.5);
        enrich    = (cP99 - bg) / dilute;
        if (mode == modes[0]) { lo = cMed; hi = maxOf(cMed + kSD * cSd, cMed + 3); }
        else                  { lo = cMed; hi = maxOf(cP99, cMed + 3); }

        tooDimNow = (meanAbove < dimFloor);
        softClump = (minfer > maxW) || (feret > maxL);

        scoreable = 1; fDim = 0; fDense = 0; fUnsure = 0; n = 0; nRej = 0;
        excludedBy = "none";
        fx = newArray(0); fy = newArray(0);

        selectWindow(fieldId);
        roiManager("Show None");
        roiManager("select", c);
        Overlay.remove;
        Overlay.addSelection("yellow", 2);
        setFont("SansSerif", 16, "bold");
        setColor("yellow");
        Overlay.drawString("cell " + (c + 1), rx, maxOf(ry - 6, 18));
        Overlay.show;
        run("Select None");
        roiManager("Show None");
        setLocation(0, 0, winW, winH);
        run("Set... ", "zoom=" + cellZoom + " x=" + cx + " y=" + cy);
        if (isStack) {
            Stack.setDisplayMode("color");
            Stack.setChannel(chFluo);
        }
        run("Red");
        setMinAndMax(lo, hi);
        setTool("multipoint");

        Dialog.createNonBlocking("Cell " + (c + 1) + "/" + nCell +
                                 "   field " + (f + 1) + "/" + nThis);
        Dialog.addMessage("Click each focus in the yellow cell, then press OK.\n" +
            "No foci: press OK with nothing clicked (a genuine zero).\n \n" +
            "length " + d2s(feret, 2) + " um    width " + d2s(minfer, 2) + " um\n" +
            "mean above background " + d2s(meanAbove, 1));
        Dialog.addCheckbox("Condensate fills the cell (no dilute phase left)", false);
        Dialog.addCheckbox("Not sure this is a single cell - exclude", softClump);
        Dialog.addCheckbox("Too dim or too noisy to score - exclude", tooDimNow);
        Dialog.setLocation(dlgX, 100);
        Dialog.show();
        fDense  = Dialog.getCheckbox();
        fUnsure = Dialog.getCheckbox();
        tooDim  = Dialog.getCheckbox();

        if (tooDim)  { fDim = 1; scoreable = 0; }
        if (fUnsure) { scoreable = 0; }
        if (fDense && denseExcl) { scoreable = 0; }
        if (scoreable == 0) {
            reasons = "";
            if (tooDim)              reasons = reasons + "_dim";
            if (fUnsure)             reasons = reasons + "_unsure";
            if (fDense && denseExcl) reasons = reasons + "_dense";
            excludedBy = "you" + reasons;
        }

        if (selectionType == 10) {
            getSelectionCoordinates(sx, sy);
            roiManager("select", c);
            if (fociTolPx > 0)
                run("Enlarge...", "enlarge=" + fociTolPx + " pixel");
            for (k = 0; k < sx.length; k++) {
                if (selectionContains(sx[k], sy[k])) {
                    fx[fx.length] = sx[k]; fy[fy.length] = sy[k];
                } else {
                    nRej++;
                }
            }
            n = fx.length;
            if (n > 0) {
                selectWindow(fieldId);
                makeSelection("point", fx, fy);
                roiManager("add");
                roiManager("select", roiManager("count") - 1);
                roiManager("rename", "foci_cell" + (c + 1));
            }
        }
        selectWindow(fieldId);
        Overlay.remove;
        roiManager("Show None");
        run("Select None");

        fpu = 0;
        if (feret > 0 && scoreable == 1) fpu = n / feret;

        File.append(fieldId + "," + fname + ",\"" + sub + "\"," + d2s(pw, 5) + "," +
            "\"" + unit + "\"," + (c + 1) + ",manual," +
            d2s(area, 4) + "," + d2s(feret, 4) + "," + d2s(minfer, 4) + "," +
            d2s(bg, 2) + "," + d2s(cMean, 2) + "," + d2s(cMed, 2) + "," +
            d2s(cSd, 2) + "," + d2s(cP99, 2) + "," + d2s(cMax, 2) + "," +
            d2s(enrich, 3) + "," +
            d2s(lo, 2) + "," + d2s(hi, 2) + ",\"" + mode + "\"," +
            scoreable + "," + excludedBy + "," +
            fDim + "," + fDense + "," + fUnsure + "," +
            n + "," + nRej + "," + d2s(fpu, 4), scrCell);
        for (k = 0; k < n; k++)
            File.append(fieldId + "," + fname + "," + (c + 1) + "," + (k + 1) + "," +
                d2s(fx[k], 2) + "," + d2s(fy[k], 2) + "," +
                d2s(fx[k] * pw, 4) + "," + d2s(fy[k] * ph, 4), scrFoci);
        if (scoreable == 1) { nCellsDone++; nFociDone += n; }
    }

    roiManager("deselect");
    roiManager("save", roiDir + File.separator + fieldId + "_ROI.zip");
    mergeInto(scrCell, cellCsv);
    mergeInto(scrFoci, fociCsv);
    File.append(fieldId + "," + fname + ",\"" + sub + "\"," + nCell, doneCsv);
    nFieldsDone++;
}
close("*");
roiManager("reset");
print("fields finished: " + nFieldsDone + "   cells scored: " + nCellsDone +
      "   foci counted: " + nFociDone);

function listCzi(dir, acc) {
    l = getFileList(dir);
    for (i = 0; i < l.length; i++) {
        p = dir + File.separator + l[i];
        if (File.isDirectory(p)) acc = listCzi(p, acc);
        else if (endsWith(toLowerCase(l[i]), ".czi")) acc[acc.length] = p;
    }
    return acc;
}

function pctileHere(frac) {
    if (bitDepth() == 16) nb = 65536;
    else                  nb = 256;
    getHistogram(v, cnt, nb);
    tot = 0;
    for (i = 0; i < cnt.length; i++) tot += cnt[i];
    if (tot == 0) return 0;
    acc = 0;
    for (i = 0; i < cnt.length; i++) {
        acc += cnt[i];
        if (acc >= frac * tot) return v[i];
    }
    return v[cnt.length - 1];
}

function mergeInto(src, dst) {
    if (!File.exists(src)) return;
    s = File.openAsString(src);
    while (endsWith(s, "\n") || endsWith(s, "\r"))
        s = substring(s, 0, lengthOf(s) - 1);
    if (lengthOf(s) > 0) File.append(s, dst);
    File.delete(src);
}

function firstLineOf(p) {
    s = File.openAsString(p);
    k = indexOf(s, "\n");
    if (k >= 0) s = substring(s, 0, k);
    while (endsWith(s, "\r")) s = substring(s, 0, lengthOf(s) - 1);
    return s;
}

function stripPrefix(str, pre) {
    if (lengthOf(str) >= lengthOf(pre) && substring(str, 0, lengthOf(pre)) == pre)
        return substring(str, lengthOf(pre));
    return str;
}

function toSlash(str) {
    out = "";
    for (i = 0; i < lengthOf(str); i++) {
        ch = substring(str, i, i + 1);
        if (ch == "\\") out = out + "/";
        else out = out + ch;
    }
    return out;
}

function stripExt(nm) {
    if (endsWith(toLowerCase(nm), ".czi"))
        return substring(nm, 0, lengthOf(nm) - 4);
    return nm;
}
