var CRITERION = "Budding = discrete outward protrusion meeting the body at a concave neck";
var MIN_DIAM_UM = 70;
var UM_PER_PX = 0.8848;
var SEED = 1;
var ADD_PAGE = 8;
var FONT_SIZE = 40;

csvPath = File.openDialog("Select AllDetections_clean.csv");
if (csvPath == "") exit("cancelled");
imgDir = getDirectory("Select the folder of ORIGINAL images");
if (imgDir == "") exit("cancelled");
outDir = getDirectory("Select an output folder for the scores");
if (outDir == "") exit("cancelled");
outPath = outDir + "budding_scores.csv";

lines = split(File.openAsString(csvPath), "\n");
if (lines.length < 2) exit("CSV looks empty");
hdr = split(replace(lines[0], "\r", ""), ",");
cFile = -1; cX = -1; cY = -1; cW = -1; cH = -1; cCls = -1; cConf = -1; cFG = -1;
for (i = 0; i < hdr.length; i++) {
    n = String.trim(hdr[i]);
    if (n == "filename")   cFile = i;
    if (n == "xc")         cX = i;
    if (n == "yc")         cY = i;
    if (n == "w")          cW = i;
    if (n == "h")          cH = i;
    if (n == "classorg" || n == "class") cCls = i;
    if (n == "confidence") cConf = i;
    if (n == "field_group") cFG = i;
}
if (cFile < 0 || cX < 0 || cY < 0 || cW < 0 || cH < 0 || cFG < 0)
    exit("CSV must contain filename, xc, yc, w, h and field_group columns.");

nDet = lines.length - 1;
dFile = newArray(nDet); dX = newArray(nDet); dY = newArray(nDet);
dW = newArray(nDet); dH = newArray(nDet); dCls = newArray(nDet);
dConf = newArray(nDet); dKey = newArray(nDet);
k = 0;
for (i = 1; i < lines.length; i++) {
    ln = replace(lines[i], "\r", "");
    if (lengthOf(String.trim(ln)) == 0) continue;
    f = split(ln, ",");
    if (f.length <= cH) continue;
    dFile[k] = String.trim(f[cFile]);
    dX[k] = parseFloat(f[cX]);  dY[k] = parseFloat(f[cY]);
    dW[k] = parseFloat(f[cW]);  dH[k] = parseFloat(f[cH]);
    if (cCls >= 0)  dCls[k] = String.trim(f[cCls]);  else dCls[k] = "NA";
    if (cConf >= 0) dConf[k] = String.trim(f[cConf]); else dConf[k] = "NA";
    dKey[k] = String.trim(f[cFG]);
    k++;
}
nDet = k;
print("\\Clear");
print("loaded " + nDet + " detections");

dStem = newArray(nDet);
for (i = 0; i < nDet; i++) dStem[i] = stripExt(dFile[i]);

stems = newArray(nDet);
nStem = 0;
for (i = 0; i < nDet; i++) {
    seen = false;
    for (j = 0; j < nStem; j++) if (stems[j] == dKey[i]) { seen = true; break; }
    if (!seen) { stems[nStem] = dKey[i]; nStem++; }
}
stems = Array.trim(stems, nStem);

done = newArray(0);
if (File.exists(outPath)) {
    prev = split(File.openAsString(outPath), "\n");
    for (i = 1; i < prev.length; i++) {
        p = split(prev[i], ",");
        if (p.length > 0) {
            s = stripExt(String.trim(p[0]));
            key = s;
            for (q = 0; q < nDet; q++) {
                if (dStem[q] == s) { key = dKey[q]; break; }
            }
            if (!inList(done, key)) done = Array.concat(done, key);
        }
    }
    print("resuming: " + done.length + " fields already scored");
} else {
    File.append("filename,det_index,classorg,confidence,xc,yc,w,h,score,reviewed,min_diam_um,source,swept,criterion", outPath);
}

order = newArray(nStem);
for (i = 0; i < nStem; i++) order[i] = i;
random("seed", SEED);
for (i = nStem - 1; i > 0; i--) {
    j = floor(random() * (i + 1));
    t = order[i]; order[i] = order[j]; order[j] = t;
}

setOption("BlackBackground", false);
classes = newArray("Unclassified", "Cyst", "EarlyOrganoid", "LateOrganoid", "Spheroid");
for (oi = 0; oi < nStem; oi++) {
    stem = stems[order[oi]];
    if (inList(done, stem)) continue;

    idx = newArray(nDet); nThis = 0;
    for (i = 0; i < nDet; i++) {
        if (dKey[i] == stem) { idx[nThis] = i; nThis++; }
    }
    idx = Array.trim(idx, nThis);

    planeStems = newArray(nThis); nPlanes = 0;
    for (m = 0; m < nThis; m++) {
        s2 = dStem[idx[m]];
        dupP = false;
        for (q = 0; q < nPlanes; q++) if (planeStems[q] == s2) { dupP = true; break; }
        if (!dupP) { planeStems[nPlanes] = s2; nPlanes++; }
    }
    planeStems = Array.trim(planeStems, nPlanes);
    Array.sort(planeStems);

    close("*");
    nOpened = 0;
    for (q = 0; q < nPlanes; q++) {
        p2 = findImage(imgDir, planeStems[q]);
        if (p2 != "") { open(p2); nOpened++; }
    }
    if (nOpened == 0) { print("SKIP (no image found): " + stem); continue; }
    if (nOpened > 1) run("Images to Stack", "name=field title=[] use");
    W = getWidth(); H = getHeight();
    run("Enhance Contrast", "saturated=0.35");

    big = newArray(nThis); nBig = 0;
    for (m = 0; m < nThis; m++) {
        i = idx[m];
        dUm = sqrt((dW[i] * W) * (dH[i] * H)) * UM_PER_PX;
        big[m] = (dUm >= MIN_DIAM_UM);
        if (big[m]) nBig++;
    }

    Overlay.remove;
    setFont("SansSerif", FONT_SIZE, "bold");
    for (m = 0; m < nThis; m++) {
        i = idx[m];
        bx = (dX[i] - dW[i] / 2) * W;  by = (dY[i] - dH[i] / 2) * H;
        if (big[m]) {
            setColor("cyan");
            Overlay.drawRect(bx, by, dW[i] * W, dH[i] * H);
            Overlay.drawString("" + (m + 1), bx, maxOf(by, FONT_SIZE));
        } else {
            setColor("#555555");
            Overlay.drawRect(bx, by, dW[i] * W, dH[i] * H);
        }
    }
    Overlay.show;
    run("Select None");

    title = "field " + (oi + 1) + " of " + nStem + "  [blinded]";
    rename(title);
    setLocation(0, 0);
    run("Set... ", "zoom=33 x=" + (W / 2) + " y=" + (H / 2));
    getLocationAndSize(wx, wy, ww, wh);
    dlgX = wx + ww + 10;
    if (dlgX > screenWidth - 430) dlgX = maxOf(0, screenWidth - 430);
    setTool("multipoint");

    Dialog.createNonBlocking("Score  -  " + title);
    Dialog.setLocation(dlgX, maxOf(0, wy + 40));
    Dialog.addMessage(CRITERION);
    Dialog.addMessage(nBig + " structures to judge (of " + nThis + ");\n" +
        "dim boxes are < " + MIN_DIAM_UM + " um and scored not_budding.\n" +
        "Click each BUDDING structure. Then press OK.");
    Dialog.addString("EXCLUDE numbers (debris/clipped, optional):", "", 30);
    Dialog.addCheckbox("stop after this field", false);
    Dialog.show();
    excStr = Dialog.getString();
    stopNow = Dialog.getCheckbox();
    exc = parseIndexList(excStr, nThis);

    bud = newArray(0);
    if (selectionType() == 10) {
        getSelectionCoordinates(px, py);
        for (q = 0; q < px.length; q++) {
            hit = -1; hitArea = 1e12;
            for (m = 0; m < nThis; m++) {
                i = idx[m];
                bx0 = (dX[i] - dW[i] / 2) * W;  by0 = (dY[i] - dH[i] / 2) * H;
                bx1 = (dX[i] + dW[i] / 2) * W;  by1 = (dY[i] + dH[i] / 2) * H;
                if (px[q] >= bx0 && px[q] <= bx1 && py[q] >= by0 && py[q] <= by1) {
                    ar = (bx1 - bx0) * (by1 - by0);
                    if (ar < hitArea) { hitArea = ar; hit = m + 1; }
                }
            }
            if (hit > 0 && !inList(bud, hit)) bud = Array.concat(bud, hit);
        }
    }

    makeRectangle(0, 0, 1, 1);
    run("Select None");
    Overlay.remove;
    for (m = 0; m < nThis; m++) {
        i = idx[m];
        setColor("cyan");
        Overlay.drawRect((dX[i] - dW[i] / 2) * W, (dY[i] - dH[i] / 2) * H,
                         dW[i] * W, dH[i] * H);
    }
    Overlay.show;
    roiManager("reset");
    setTool("rectangle");
    Dialog.createNonBlocking("Missed structures?  -  " + title);
    Dialog.setLocation(dlgX, maxOf(0, wy + 40));
    Dialog.addMessage("Cyan boxes are already counted, across both focal planes.\n" +
        "Drag a rectangle round any structure without a box, press t.\n" +
        "Sweep the whole field every time. Nothing to add? Press OK.");
    Dialog.show();

    nAdd = roiManager("count");
    addX = newArray(nAdd); addY = newArray(nAdd); addW = newArray(nAdd);
    addH = newArray(nAdd); addCls = newArray(nAdd); addBud = newArray(nAdd);
    for (k = 0; k < nAdd; k++) {
        roiManager("select", k);
        getSelectionBounds(sx, sy, sw, sh);
        addX[k] = (sx + sw / 2) / W;
        addY[k] = (sy + sh / 2) / H;
        addW[k] = sw / W;
        addH[k] = sh / H;
    }
    for (p0 = 0; p0 < nAdd; p0 += ADD_PAGE) {
        p1 = minOf(p0 + ADD_PAGE, nAdd);
        makeRectangle(0, 0, 1, 1);
        run("Select None");
        Overlay.remove;
        setFont("SansSerif", FONT_SIZE, "bold");
        for (k = 0; k < nAdd; k++) {
            bx = (addX[k] - addW[k] / 2) * W;
            by = (addY[k] - addH[k] / 2) * H;
            if (k >= p0 && k < p1) setColor("green"); else setColor("#2E7D32");
            Overlay.drawRect(bx, by, addW[k] * W, addH[k] * H);
            if (k >= p0 && k < p1) {
                setColor("red");
                Overlay.drawString("A" + (k + 1), bx, maxOf(by, FONT_SIZE));
            }
        }
        Overlay.show;
        Dialog.createNonBlocking("Classify A" + (p0 + 1) + "-A" + p1 + " of " + nAdd);
        Dialog.setLocation(dlgX, maxOf(0, wy + 40));
        Dialog.addMessage("Leave as Unclassified if the type is uncertain.");
        for (k = p0; k < p1; k++) {
            Dialog.addChoice("A" + (k + 1), classes, "Unclassified");
            Dialog.addToSameRow();
            Dialog.addCheckbox("budding", false);
        }
        Dialog.show();
        for (k = p0; k < p1; k++) {
            addCls[k] = Dialog.getChoice();
            if (Dialog.getCheckbox()) addBud[k] = 1; else addBud[k] = 0;
        }
    }
    roiManager("reset");

    for (m = 0; m < nThis; m++) {
        i = idx[m];
        sc = "not_budding";
        if (inList(exc, m + 1))      sc = "excluded";
        else if (inList(bud, m + 1)) sc = "budding";
        rev = "no";
        if (big[m] || inList(bud, m + 1)) rev = "yes";
        File.append(dFile[i] + "," + (m + 1) + "," + dCls[i] + "," + dConf[i] + "," +
                    dX[i] + "," + dY[i] + "," + dW[i] + "," + dH[i] + "," + sc +
                    "," + rev + "," + MIN_DIAM_UM + ",tellu,yes,\"" +
                    CRITERION + "\"", outPath);
    }
    addStem = planeStems[0];
    for (k = 0; k < nAdd; k++) {
        scAdd = "not_budding";
        if (addBud[k] == 1) scAdd = "budding";
        File.append(addStem + ".txt," + (1001 + k) + "," + addCls[k] + ",," +
                    addX[k] + "," + addY[k] + "," + addW[k] + "," + addH[k] +
                    "," + scAdd + ",yes," + MIN_DIAM_UM + ",manual,yes,\"" +
                    CRITERION + "\"", outPath);
    }
    print(title + ": " + nThis + " detections, " + bud.length + " budding, " +
          exc.length + " excluded, " + nAdd + " added");
    if (stopNow) break;
}
close("*");
print("done. scores written to: " + outPath);

function stripExt(name) {
    d = lastIndexOf(name, ".");
    if (d > 0) return substring(name, 0, d);
    return name;
}

function findImage(dir, stem) {
    exts = newArray(".jpg", ".jpeg", ".JPG", ".png", ".tif", ".tiff", ".TIF", ".bmp");
    v = newArray(stem, replace(stem, "-", "_"), replace(stem, "_", "-"));
    for (a = 0; a < v.length; a++)
        for (b = 0; b < exts.length; b++)
            if (File.exists(dir + v[a] + exts[b])) return dir + v[a] + exts[b];
    return "";
}

function parseIndexList(s, nMax) {
    out = newArray(0);
    s = String.trim(s);
    if (lengthOf(s) == 0) return out;
    s = replace(s, ";", ",");
    s = replace(s, " ", ",");
    parts = split(s, ",");
    for (i = 0; i < parts.length; i++) {
        p = String.trim(parts[i]);
        if (lengthOf(p) == 0) continue;
        if (indexOf(p, "-") > 0) {
            ab = split(p, "-");
            if (ab.length == 2) {
                a = parseInt(String.trim(ab[0]));
                b = parseInt(String.trim(ab[1]));
                if (!isNaN(a) && !isNaN(b))
                    for (v = minOf(a, b); v <= maxOf(a, b); v++)
                        if (v >= 1 && v <= nMax) out = Array.concat(out, v);
            }
        } else {
            v = parseInt(p);
            if (!isNaN(v) && v >= 1 && v <= nMax) out = Array.concat(out, v);
        }
    }
    return out;
}

function inList(arr, v) {
    for (i = 0; i < arr.length; i++) if (arr[i] == v) return true;
    return false;
}
