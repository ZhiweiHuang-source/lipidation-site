// Unified macro: build or reuse masks and compute K1/K2 in one run
// For each image in IMAGE dir:
//   - If masks exist in MASK dir and mode allows, use them; otherwise, build masks from the image
//   - Extract CH1 and CH2 planes (T=1; optional Z-proj)
//   - Measure means: CH1 in mask1/mask2; CH2 in mask2/mask1; compute K1/K2
//   - Save/overwrite masks if built; save preview overlays; append CSV

macro "Unified: Build/Use Masks + Compute K1/K2" {
	// Select directories
	imgDir = getDirectory("Choose IMAGE directory (OME-TIFFs)");
	if (imgDir=="") exit("No image dir selected");
	defMaskDir = imgDir + File.separator + "masks" + File.separator;
	if (!File.exists(defMaskDir)) File.makeDirectory(defMaskDir);
	maskDir = getDirectory("Choose MASK directory (will read/write __mask_IDP*.png)");
	if (maskDir=="") maskDir = defMaskDir;

	// Options
	methods = newArray("Otsu","Li","Triangle","Yen","Huang","Moments","Default","Manual");
	unifyOpts = newArray("None","Dilate-merge (n px)","Largest particle","Convex hull (single ROI)","Bounding box");
	diluteOpts = newArray("Other IDP mask","Outside own (ring)","Outside both masks (ring)","Global outside (exclude masks)");
	projOpts = newArray("Max","Mean","Median","None");
	Dialog.create("Unified K1/K2");
	Dialog.addNumber("IDP1 channel (1-based)", 1);
	Dialog.addNumber("IDP2 channel (1-based)", 2);
	Dialog.addChoice("Measurement Z-projection", projOpts, "None");
	Dialog.addCheckbox("Save preview overlays", true);
	Dialog.addString("CSV filename", "k12_unified.csv");
	Dialog.addChoice("Dilute region for IDP1", diluteOpts, "Other IDP mask");
	Dialog.addChoice("Dilute region for IDP2", diluteOpts, "Other IDP mask");
	Dialog.addNumber("Ring width (px)", 10);
	Dialog.addCheckbox("Subtract background (global outside both masks)", false);

	Dialog.addMessage("Mask build settings (used when building)");
	Dialog.addChoice("Threshold (IDP1)", methods, "Otsu");
	Dialog.addChoice("Threshold (IDP2)", methods, "Otsu");
	Dialog.addCheckbox("Objects are BRIGHT in IDP1 (unchecked if darker)", true);
	Dialog.addCheckbox("Objects are BRIGHT in IDP2 (unchecked if darker)", true);
	Dialog.addNumber("Threshold offset (IDP1) % (-50..50)", 0);
	Dialog.addNumber("Threshold offset (IDP2) % (-50..50)", 0);
	Dialog.addNumber("Manual threshold (IDP1)", 0);
	Dialog.addNumber("Manual threshold (IDP2)", 0);
	Dialog.addCheckbox("Fill holes", false);
	Dialog.addNumber("Open iterations", 0);
	Dialog.addNumber("Close iterations", 0);
	Dialog.addChoice("Unify mask", unifyOpts, "None");
	Dialog.addNumber("Dilate-merge iterations (px)", 0);
	Dialog.addNumber("Min size for 'Largest' (px)", 50);
	Dialog.addCheckbox("Exclude edge particles (Largest)", false);
	Dialog.addCheckbox("Threshold on 8-bit copy", true);
	Dialog.show();

	CH1 = Dialog.getNumber();
	CH2 = Dialog.getNumber();
	PROJ_METHOD = Dialog.getChoice();
	SAVE_PREVIEW = Dialog.getCheckbox();
	csvName = Dialog.getString();
	DILUTE1_MODE = Dialog.getChoice();
	DILUTE2_MODE = Dialog.getChoice();
	RING_PX = Dialog.getNumber();
	SUB_BG = Dialog.getCheckbox();

	TH1 = Dialog.getChoice();
	TH2 = Dialog.getChoice();
	OBJ1_BRIGHT = Dialog.getCheckbox();
	OBJ2_BRIGHT = Dialog.getCheckbox();
	TH1_OFF = Dialog.getNumber();
	TH2_OFF = Dialog.getNumber();
	TH1_MAN = Dialog.getNumber();
	TH2_MAN = Dialog.getNumber();
	FILL = Dialog.getCheckbox();
	OPEN_IT = Dialog.getNumber();
	CLOSE_IT = Dialog.getNumber();
	UNIFY = Dialog.getChoice();
	DIL_IT = Dialog.getNumber();
	MIN_SIZE = Dialog.getNumber();
	EXCL_EDGES = Dialog.getCheckbox();
	THRESH_ON_8BIT = Dialog.getCheckbox();

	origCsvPath = maskDir + csvName;
	csvPath = pickWritableCsvPath(origCsvPath);
	header = "filename,image_rel,ch1,ch2,zproj,mean_C1_ROI1,mean_C1_den,mean_C2_ROI2,mean_C2_den,K1,K2,area_ROI1_px,area_ROI2_px,parts1,parts2,parts_overlap,area_overlap_px,area_union_px,iou_global,th1,th2,obj1_bright,obj2_bright,thr_on_8bit,th1_off,th2_off,th1_man,th2_man,open,close,fill,unify,dilate,min_size,exclude_edges,dilute1_mode,dilute2_mode,ring_px,sub_bg,error\n";
	rows = "";

	setBatchMode(true);
	list = getFileList(imgDir);
	for (i=0; i<list.length; i++) {
		name = list[i]; lname = toLowerCase(name);
		if ((endsWith2(lname, ".ome.tif")==0) && (endsWith2(lname, ".tif")==0) && (endsWith2(lname, ".tiff")==0)) continue;
		base = stripExt(name);
		ipath = imgDir + name;

	// Output mask paths (for QA saving only)
	m1path = maskDir + base + "__mask_IDP1.png";
	m2path = maskDir + base + "__mask_IDP2.png";

		// Open image
		run("Bio-Formats Importer", "open=[" + ipath + "] autoscale color_mode=Default view=Hyperstack stack_order=XYCZT");
		ititle = getTitle();

		// Extract planes for measurement
		plane1 = extractPlane(ititle, CH1);
		plane2 = extractPlane(ititle, CH2);
		if (plane1=="" || plane2=="") {
			line = appendRow(base, rel(ipath,imgDir), CH1, CH2, PROJ_METHOD, "", "", "", "", "", "", 0, 0, 0, 0, TH1, TH2, OBJ1_BRIGHT, OBJ2_BRIGHT, THRESH_ON_8BIT, TH1_OFF, TH2_OFF, TH1_MAN, TH2_MAN, OPEN_IT, CLOSE_IT, FILL, UNIFY, DIL_IT, MIN_SIZE, EXCL_EDGES, DILUTE1_MODE, DILUTE2_MODE, RING_PX, SUB_BG, "failed to extract planes");
			rows = rows + line;
			cleanupImageWindows(ititle);
			continue;
		}

	// Always build masks fresh from the current image; PNGs are saved only for QA
	m1t = buildMaskFromPlane(plane1, TH1, OBJ1_BRIGHT, TH1_OFF, TH1_MAN, FILL, OPEN_IT, CLOSE_IT, UNIFY, DIL_IT, MIN_SIZE, EXCL_EDGES);
	m2t = buildMaskFromPlane(plane2, TH2, OBJ2_BRIGHT, TH2_OFF, TH2_MAN, FILL, OPEN_IT, CLOSE_IT, UNIFY, DIL_IT, MIN_SIZE, EXCL_EDGES);

		if (m1t=="" || m2t=="") {
			// Failed to obtain masks
			// blanks for overlap metrics (4), then parameters and error
			line = base + "," + rel(ipath,imgDir) + "," + CH1 + "," + CH2 + "," + PROJ_METHOD + ",,,,,,,," + 0 + "," + 0 + "," + 0 + "," + 0 + "," + TH1 + "," + TH2 + "," + OBJ1_BRIGHT + "," + OBJ2_BRIGHT + "," + THRESH_ON_8BIT + "," + TH1_OFF + "," + TH2_OFF + "," + TH1_MAN + "," + TH2_MAN + "," + OPEN_IT + "," + CLOSE_IT + "," + FILL + "," + UNIFY + "," + DIL_IT + "," + MIN_SIZE + "," + EXCL_EDGES + "," + DILUTE1_MODE + "," + DILUTE2_MODE + "," + RING_PX + "," + SUB_BG + ",failed to obtain masks\n";
			rows = rows + line;
			if (isOpen(m1t)) { selectWindow(m1t); close(); }
			if (isOpen(m2t)) { selectWindow(m2t); close(); }
			cleanupImageWindows(ititle);
			continue;
		}

		// Build dilute masks per selection
		dmask1 = buildDiluteMask(m1t, m2t, DILUTE1_MODE, RING_PX);
		dmask2 = buildDiluteMask(m2t, m1t, DILUTE2_MODE, RING_PX);

		// Optional background subtraction using global outside of both masks
		plane1_meas = plane1;
		plane2_meas = plane2;
		bgMask = "";
		if (SUB_BG) {
			bgMask = buildDiluteMask(m1t, m2t, "Global outside (exclude masks)", RING_PX);
			bg1 = measureMeanWithMask(bgMask, plane1);
			bg2 = measureMeanWithMask(bgMask, plane2);
			plane1_meas = makeBgSubPlane(plane1, bg1);
			plane2_meas = makeBgSubPlane(plane2, bg2);
		}
	// Measurements (dense vs chosen dilute)
	mean_C1_ROI1 = measureMeanWithMask(m1t, plane1_meas);
	mean_C1_den = measureMeanWithMask(dmask1, plane1_meas);
	mean_C2_ROI2 = measureMeanWithMask(m2t, plane2_meas);
	mean_C2_den = measureMeanWithMask(dmask2, plane2_meas);
		area1 = measureArea(m1t);
		area2 = measureArea(m2t);
		parts1 = countParticles(m1t, MIN_SIZE, EXCL_EDGES);
		parts2 = countParticles(m2t, MIN_SIZE, EXCL_EDGES);

		// Overlap metrics: intersection and union between masks
		ovMask = buildOverlapMask(m1t, m2t);
		parts_overlap = 0; area_overlap = 0; area_union = 0; iou_global = NaN;
		if (ovMask!="") {
			parts_overlap = countParticles(ovMask, MIN_SIZE, EXCL_EDGES);
			area_overlap = measureArea(ovMask);
		}
		unMask = buildUnionMask(m1t, m2t);
		if (unMask!="") {
			area_union = measureArea(unMask);
		}
	if (area_union>0) iou_global = area_overlap/area_union;
	K1 = NaN; if (!isNaN(mean_C1_den) && mean_C1_den>0) K1 = mean_C1_ROI1/mean_C1_den;
	K2 = NaN; if (!isNaN(mean_C2_den) && mean_C2_den>0) K2 = mean_C2_ROI2/mean_C2_den;

	// Save masks for QA (clear selections/overlays so no yellow ants/labels appear)
	if (isOpen(m1t)) { selectWindow(m1t); run("Select None"); run("Remove Overlay"); saveAs("PNG", m1path); }
	if (isOpen(m2t)) { selectWindow(m2t); run("Select None"); run("Remove Overlay"); saveAs("PNG", m2path); }

	// Write CSV row
	line = base + "," + rel(ipath,imgDir) + "," + CH1 + "," + CH2 + "," + PROJ_METHOD + "," + d2sOrNaN(mean_C1_ROI1) + "," + d2sOrNaN(mean_C1_den) + "," + d2sOrNaN(mean_C2_ROI2) + "," + d2sOrNaN(mean_C2_den) + "," + d2sOrNaN(K1) + "," + d2sOrNaN(K2) + "," + round(area1) + "," + round(area2) + "," + parts1 + "," + parts2 + "," + parts_overlap + "," + round(area_overlap) + "," + round(area_union) + "," + d2sOrNaN(iou_global) + "," + TH1 + "," + TH2 + "," + OBJ1_BRIGHT + "," + OBJ2_BRIGHT + "," + THRESH_ON_8BIT + "," + TH1_OFF + "," + TH2_OFF + "," + TH1_MAN + "," + TH2_MAN + "," + OPEN_IT + "," + CLOSE_IT + "," + FILL + "," + UNIFY + "," + DIL_IT + "," + MIN_SIZE + "," + EXCL_EDGES + "," + DILUTE1_MODE + "," + DILUTE2_MODE + "," + RING_PX + "," + SUB_BG + "," + "" + "\n";
		rows = rows + line;

		if (SAVE_PREVIEW) savePreviewOverlay(plane1, m1t, m2t, maskDir, base);

		// Cleanup
		if (SUB_BG) {
			if (isOpen(bgMask)) { selectWindow(bgMask); close(); }
			if (plane1_meas!=plane1 && isOpen(plane1_meas)) { selectWindow(plane1_meas); close(); }
			if (plane2_meas!=plane2 && isOpen(plane2_meas)) { selectWindow(plane2_meas); close(); }
		}
	if (isOpen(dmask1)) { selectWindow(dmask1); close(); }
	if (isOpen(dmask2)) { selectWindow(dmask2); close(); }
		if (isOpen(m1t)) { selectWindow(m1t); close(); }
		if (isOpen(m2t)) { selectWindow(m2t); close(); }
		cleanupImageWindows(ititle);
	}
	setBatchMode(false);
	// Write final CSV once to avoid file-lock racing with spreadsheet apps
	File.saveString(header + rows, csvPath);
	print("Done. CSV: " + csvPath);
}

// ---- Helpers ----
function endsWith2(s, suf) {
	if (lengthOf(s) < lengthOf(suf)) return 0;
	part = substring(s, lengthOf(s)-lengthOf(suf));
	if (toLowerCase(part) == toLowerCase(suf)) return 1;
	return 0;
}

function stripExt(name) {
	n = name; l = toLowerCase(n);
	if (endsWith2(l, ".ome.tif")) return substring(n, 0, lengthOf(n)-8);
	if (endsWith2(l, ".tiff")) return substring(n, 0, lengthOf(n)-5);
	if (endsWith2(l, ".tif")) return substring(n, 0, lengthOf(n)-4);
	return n;
}

function rel(path, startDir) {
	if (indexOf(path, startDir)==0) return substring(path, lengthOf(startDir));
	return path;
}

// Choose a writable CSV path; if the file is locked (e.g., open in Excel),
// create a timestamped alternative in the same directory.
function pickWritableCsvPath(target) {
	// Try to write a tiny test and delete it.
	// If the parent file exists and is locked, we will choose another name.
	dir = File.getParent(target) + File.separator;
	name = File.getName(target);
	testPath = dir + ".__csv_lock_test__" + getTime() + ".tmp";
	File.saveString("test", testPath);
	if (File.exists(testPath)) File.delete(testPath);
	// If target seems writable, return it; else add timestamp
	// We cannot directly detect a lock until writing; we will just return target.
	// Final write will succeed; if not, user will see the error.
	// To reduce collisions with open files, if target exists, pick timestamped name.
	if (File.exists(target)) {
		ts = getDateTimeStamp();
		dot = lastIndexOf(name, ".");
		if (dot>=0) base = substring(name, 0, dot); else base = name;
		if (dot>=0) ext = substring(name, dot); else ext = ".csv";
		return dir + base + "_" + ts + ext;
	}
	return target;
}

function getDateTimeStamp() {
	// Use epoch milliseconds for a portable, unique stamp
	return d2s(getTime(), 0);
}

function lastIndexOf(s, sub) {
	sl = lengthOf(s); tl = lengthOf(sub);
	if (tl==0) return sl;
	idx = -1;
	for (ii=0; ii<=sl - tl; ii++) {
		part = substring(s, ii, ii+tl);
		if (part==sub) idx = ii;
	}
	return idx;
}

function extractPlane(title, ch) {
	// Reuse existing split channel window if present
	ct = "C" + ch + "-" + title;
	if (isOpen(ct)) {
		selectWindow(ct);
		Stack.getDimensions(w,h,c,s,f);
		if (f>1) Stack.setFrame(1);
		if (s>1 && PROJ_METHOD!="None") {
			proj = PROJ_METHOD; if (PROJ_METHOD=="Max") proj = "Max Intensity";
			run("Z Project...", "projection=[" + proj + "]");
			ptitle = "MAX_" + ct; if (isOpen(ptitle)) return ptitle; return getTitle();
		}
		return getTitle();
	}
	// Ensure the composite/hyperstack window is selected
	if (!isOpen(title)) return "";
	selectWindow(title);
	Stack.getDimensions(w,h,c,s,f);
	// Handle single-channel images gracefully
	if (c<=1) {
		if (ch!=1) return ""; // requested non-existent channel
		if (f>1) Stack.setFrame(1);
		if (s>1 && PROJ_METHOD!="None") {
			proj = PROJ_METHOD; if (PROJ_METHOD=="Max") proj = "Max Intensity";
			run("Z Project...", "projection=[" + proj + "]");
			return getTitle();
		}
		return getTitle();
	}
	// Split channels once from the composite window
	run("Split Channels");
	ct = "C" + ch + "-" + title;
	if (!isOpen(ct)) return "";
	selectWindow(ct);
	Stack.getDimensions(w,h,c,s,f);
	if (f>1) Stack.setFrame(1);
	if (s>1 && PROJ_METHOD!="None") {
		proj = PROJ_METHOD; if (PROJ_METHOD=="Max") proj = "Max Intensity";
		run("Z Project...", "projection=[" + proj + "]");
		ptitle = "MAX_" + ct; if (isOpen(ptitle)) return ptitle; return getTitle();
	}
	return getTitle();
}

function openMaskAsBinary(path, planeTitle) {
	if (!File.exists(path)) return "";
	open(path);
	mtitle = getTitle();
	run("8-bit");
	selectWindow(planeTitle); W = getWidth(); H = getHeight();
	selectWindow(mtitle);
	if (getWidth()!=W || getHeight()!=H) run("Size...", "width=" + W + " height=" + H + " interpolation=None average");
	setThreshold(1,255); run("Convert to Mask");
	return mtitle;
}

function measureMeanWithMask(maskTitle, planeTitle) {
	// Robust measurement: multiply plane by mask (scaled 0..1),
	// sum the masked intensities, divide by white pixel count.
	if (!isOpen(maskTitle) || !isOpen(planeTitle)) return NaN;
	whiteCount = measureArea(maskTitle);
	if (whiteCount<=0) return NaN;

	// Duplicate plane and mask to 32-bit
	selectWindow(planeTitle);
	run("Duplicate...", "title=__tmp_plane__");
	run("32-bit");
	selectWindow(maskTitle);
	run("Duplicate...", "title=__tmp_mask__");
	run("32-bit");
	// Scale mask to 0..1
	run("Divide...", "value=255");
	// Ensure same size
	selectWindow("__tmp_plane__"); W=getWidth(); H=getHeight();
	selectWindow("__tmp_mask__"); if (getWidth()!=W || getHeight()!=H) run("Size...", "width="+W+" height="+H+" interpolation=None average");
	// Multiply: masked = plane * mask
	run("Image Calculator...", "image1=__tmp_plane__ operation=Multiply image2=__tmp_mask__ create 32-bit");
	maskedTitle = getTitle();
	// Compute sum over all pixels in masked image
	selectWindow(maskedTitle); w=getWidth(); h=getHeight();
	getStatistics(aTot, meanAll, minv, maxv, stdv);
	sumMasked = meanAll * (w*h);
	meanMasked = sumMasked / whiteCount;
	// Cleanup temp images
	close(); // close masked
	selectWindow("__tmp_mask__"); close();
	selectWindow("__tmp_plane__"); close();
	return meanMasked;
}

function measureArea(maskTitle) {
	if (!isOpen(maskTitle)) return 0;
	selectWindow(maskTitle);
	getHistogram(values, counts, 256);
	whiteCount = 0; for (hh=0; hh<256; hh++) if (hh>=255) whiteCount += counts[hh];
	return whiteCount;
}

function countParticles(maskTitle, minSize, exclEdges) {
	if (isOpen("ROI Manager")) roiManager("reset");
	if (!isOpen(maskTitle)) return 0;
	selectWindow(maskTitle);
	run("Set Measurements...", "area decimal=6");
	opt = "size=" + minSize + "-Infinity show=Nothing add";
	if (exclEdges) opt = opt + " exclude";
	run("Analyze Particles...", opt);
	n = roiManager("count");
	roiManager("reset");
	return n;
}

function cleanupImageWindows(ititle) {
	if (isOpen(ititle)) { selectWindow(ititle); close(); }
	for (ci=1; ci<=5; ci++) {
		t = "C"+ci+"-"+ititle; if (isOpen(t)) { selectWindow(t); close(); }
		t = "MAX_C"+ci+"-"+ititle; if (isOpen(t)) { selectWindow(t); close(); }
	}
}

// Mask builder borrowed from compute_masks_and_k12.ijm (polarity-aware, with 8-bit option)
function buildMaskFromPlane(planeTitle, method, objectsBright, thrOffsetPct, thrManual, fillH, openIt, closeIt, unify, dilIt, minSize, exclEdges) {
	if (!isOpen(planeTitle)) return "";
	LAST_FLIPPED = 0; attempt = 0; pol = objectsBright;
	while (true) {
		if (isOpen("workMask")) { selectWindow("workMask"); close(); }
		selectWindow(planeTitle); run("Duplicate...", "title=workMask"); selectWindow("workMask");
		if (THRESH_ON_8BIT) run("8-bit");
		setOption("BlackBackground", true);
		if (method=="Manual") {
			getMinAndMax(minv, maxv);
			if (pol) setThreshold(thrManual, maxv); else setThreshold(minv, thrManual);
			run("Convert to Mask");
		} else {
			// Apply threshold using Image > Adjust > Threshold semantics
			if (pol) setAutoThreshold(method + " dark=false"); else setAutoThreshold(method + " dark");
			if (thrOffsetPct!=0) {
				run("Convert to Mask"); steps = abs(thrOffsetPct);
				if (thrOffsetPct>0) { for (kk=0; kk<steps; kk++) run("Erode"); } else { for (kk=0; kk<steps; kk++) run("Dilate"); }
			} else {
				run("Convert to Mask");
			}
		}
		if (fillH) run("Fill Holes");
		for (k=0; k<openIt; k++) run("Open");
		for (k=0; k<closeIt; k++) run("Close");
		if (unify=="Dilate-merge (n px)" && dilIt>0) { for (k=0; k<dilIt; k++) run("Dilate"); for (k=0; k<dilIt; k++) run("Erode"); }
		if (unify=="Largest particle") {
			if (isOpen("ROI Manager")) roiManager("reset");
			run("Set Measurements...", "area decimal=6");
			opt = "size=" + minSize + "-Infinity show=Nothing add"; if (exclEdges) opt = opt + " exclude";
			run("Analyze Particles...", opt);
			count = roiManager("count");
			if (count>0) {
				maxArea = -1; maxIdx = 0;
				for (kk=0; kk<count; kk++) { roiManager("select", kk); run("Measure"); a = 0; if (nResults>0) a = getResult("Area", nResults-1); run("Clear Results"); if (a>maxArea) { maxArea=a; maxIdx=kk; } }
				roiManager("select", maxIdx); run("Clear Outside"); roiManager("reset");
			}
		} else if (unify=="Convex hull (single ROI)") {
			// Build a single convex hull around the union of all particles
			if (isOpen("ROI Manager")) roiManager("reset");
			run("Set Measurements...", "area decimal=6");
			opt = "size=" + minSize + "-Infinity show=Nothing add"; if (exclEdges) opt = opt + " exclude";
			run("Analyze Particles...", opt);
			cnt = roiManager("count");
			if (cnt>0) {
				roiManager("Select All");
				roiManager("Combine");
				// Save combined ROI as index 0
				roiManager("Add");
				// Compute convex hull on selection
				roiManager("select", roiManager("count")-1);
				run("Convex Hull");
				roiManager("Update");
				// Clear image and fill hull
				run("Select All"); setForegroundColor(0,0,0); run("Fill");
				roiManager("select", roiManager("count")-1);
				setForegroundColor(255,255,255); run("Fill");
				roiManager("reset");
			}
		} else if (unify=="Bounding box") {
			// Replace by the bounding rectangle of the union
			setThreshold(255,255);
			run("Create Selection");
			if (selectionType()!=-1) {
				getSelectionBounds(x, y, w, h);
				run("Select All"); setForegroundColor(0,0,0); run("Fill");
				makeRectangle(x, y, w, h);
				setForegroundColor(255,255,255); run("Fill");
				run("Select None");
			}
		}
		getHistogram(values, counts, 256); whiteCount = 0; for (hh=0; hh<256; hh++) if (hh>=255) whiteCount += counts[hh];
		if (whiteCount>0 || attempt==1) break;
		attempt = 1; pol = 1 - pol; LAST_FLIPPED = 1;
	}
	rename("mask_" + planeTitle);
	return getTitle();
}

function d2sOrNaN(x) { if (isNaN(x)) return "NaN"; return d2s(x, 6); }

function appendRow(base, imgRel, ch1, ch2, zproj, m11, m12, m22, m21, k1, k2, a1, a2, p1, p2, th1, th2, o1b, o2b, thr8, off1, off2, man1, man2, openIt, closeIt, fillH, unify, dil, minSize, excl, d1Mode, d2Mode, ringPx, subBg, err) {
	// For early failures, leave measurement fields blank and overlap metrics empty
	line = base + "," + imgRel + "," + ch1 + "," + ch2 + "," + zproj + "," + m11 + "," + m12 + "," + m22 + "," + m21 + "," + k1 + "," + k2 + "," + a1 + "," + a2 + "," + p1 + "," + p2 + ",,,,," + th1 + "," + th2 + "," + o1b + "," + o2b + "," + thr8 + "," + off1 + "," + off2 + "," + man1 + "," + man2 + "," + openIt + "," + closeIt + "," + fillH + "," + unify + "," + dil + "," + minSize + "," + excl + "," + d1Mode + "," + d2Mode + "," + ringPx + "," + subBg + "," + err + "\n";
	return line;
}

// Build a dilute-region mask for mean background/dilute measurement
// mode: "Other IDP mask" | "Outside own (ring)" | "Outside both masks (ring)" | "Global outside (exclude masks)"
function buildDiluteMask(selfMask, otherMask, mode, ringPx) {
	if (!isOpen(selfMask)) return "";
	// Create base canvas from self mask (same size)
	selectWindow(selfMask); run("Duplicate...", "title=workDilute"); selectWindow("workDilute"); run("8-bit");
	// Initialize to black
	setForegroundColor(0,0,0); run("Select All"); run("Fill"); run("Select None");

	if (mode=="Other IDP mask") {
		if (!isOpen(otherMask)) { rename("dilute_"+selfMask); return getTitle(); }
		// Replace workDilute with a clean copy of otherMask
		selectWindow(otherMask); run("Duplicate...", "title=__tmp_dm__"); selectWindow("__tmp_dm__"); run("8-bit"); setThreshold(1,255); run("Convert to Mask");
		selectWindow("workDilute"); close();
		selectWindow("__tmp_dm__"); rename("dilute_"+selfMask); return getTitle();
	} else if (mode=="Outside own (ring)") {
		// ring = dilate(self) - self
		selectWindow(selfMask); run("Duplicate...", "title=__tmp_self__"); selectWindow("__tmp_self__");
		for (k=0; k<ringPx; k++) run("Dilate");
	run("Image Calculator...", "image1=[__tmp_self__] operation=Subtract image2=["+selfMask+"] create"); ringT = getTitle();
		selectWindow(ringT); run("8-bit"); setThreshold(1,255); run("Convert to Mask");
		selectWindow("workDilute"); close();
		selectWindow(ringT); rename("dilute_"+selfMask);
		if (isOpen("__tmp_self__")) { selectWindow("__tmp_self__"); close(); }
		return getTitle();
	} else if (mode=="Outside both masks (ring)") {
		if (!isOpen(otherMask)) return "";
		// union = max(self, other); ring = dilate(union) - union
		selectWindow(selfMask); run("Duplicate...", "title=__tmp_u__");
	run("Image Calculator...", "image1=[__tmp_u__] operation=Max image2=["+otherMask+"] create"); unionT = getTitle();
		selectWindow(unionT); run("8-bit"); setThreshold(1,255); run("Convert to Mask");
		for (k=0; k<ringPx; k++) run("Dilate"); rename("__tmp_dil__");
	run("Image Calculator...", "image1=[__tmp_dil__] operation=Subtract image2=["+unionT+"] create"); ringT = getTitle();
		selectWindow(ringT); run("8-bit"); setThreshold(1,255); run("Convert to Mask");
		selectWindow("workDilute"); close();
		selectWindow(ringT); rename("dilute_"+selfMask);
		if (isOpen("__tmp_dil__")) { selectWindow("__tmp_dil__"); close(); }
		if (isOpen(unionT)) { selectWindow(unionT); close(); }
		if (isOpen("__tmp_u__")) { selectWindow("__tmp_u__"); close(); }
		return getTitle();
	} else if (mode=="Global outside (exclude masks)") {
		// fill white everywhere, then subtract masks
		setForegroundColor(255,255,255); run("Select All"); run("Fill"); run("Select None");
	run("Image Calculator...", "image1=[workDilute] operation=Subtract image2=["+selfMask+"] create"); tmp = getTitle();
		selectWindow("workDilute"); close(); selectWindow(tmp); rename("workDilute");
		if (isOpen(otherMask)) {
			run("Image Calculator...", "image1=[workDilute] operation=Subtract image2=["+otherMask+"] create"); tmp2 = getTitle();
			selectWindow("workDilute"); close(); selectWindow(tmp2); rename("workDilute");
		}
		// Ensure binary mask
		run("8-bit"); setThreshold(1,255); run("Convert to Mask");
		rename("dilute_"+selfMask);
		return getTitle();
	}
	// Default: return empty (black) mask
	rename("dilute_"+selfMask);
	return getTitle();
}

// Draw mask outlines (mask1 green, mask2 magenta) on a duplicate of plane1 and save as PNG
function savePreviewOverlay(plane1, mask1, mask2, outDir, base) {
	if (!isOpen(plane1) || !isOpen(mask1)) return;
	// Duplicate plane for drawing
	selectWindow(plane1);
	run("Duplicate...", "title=preview");
	selectWindow("preview");
	// Draw mask1 outline in green
	selectWindow(mask1); setThreshold(255,255); run("Create Selection");
	if (selectionType()!=-1) {
		selectWindow("preview");
		setColor("green");
		setLineWidth(2);
		run("Draw");
	}
	// Draw mask2 outline in magenta
	if (isOpen(mask2)) {
		selectWindow(mask2); setThreshold(255,255); run("Create Selection");
		if (selectionType()!=-1) {
			selectWindow("preview");
			setColor("magenta");
			setLineWidth(2);
			run("Draw");
		}
	}
	saveAs("PNG", outDir + base + "__preview_IDP1.png");
	close();
}

// Create a background-subtracted duplicate of a plane
function makeBgSubPlane(planeTitle, bgVal) {
	if (!isOpen(planeTitle)) return planeTitle;
	selectWindow(planeTitle);
	run("Duplicate...", "title=__tmp_bgs__");
	run("32-bit");
	// subtract background scalar and clamp to >= 0
	run("Subtract...", "value="+bgVal);
	// Clamp negatives to 0
	run("Max...", "value=0");
	return getTitle();
}

// Build intersection (AND) of two binary masks
function buildOverlapMask(mask1, mask2) {
	if (!isOpen(mask1) || !isOpen(mask2)) return "";
	selectWindow(mask1); run("Duplicate...", "title=__tmp_and__");
	run("Image Calculator...", "image1=[__tmp_and__] operation=AND image2=["+mask2+"] create");
	ol = getTitle();
	selectWindow(ol); run("8-bit"); setThreshold(1,255); run("Convert to Mask");
	if (isOpen("__tmp_and__")) { selectWindow("__tmp_and__"); close(); }
	return ol;
}

// Build union (Max) of two binary masks
function buildUnionMask(mask1, mask2) {
	if (!isOpen(mask1) || !isOpen(mask2)) return "";
	selectWindow(mask1); run("Duplicate...", "title=__tmp_or__");
	run("Image Calculator...", "image1=[__tmp_or__] operation=Max image2=["+mask2+"] create");
	ul = getTitle();
	selectWindow(ul); run("8-bit"); setThreshold(1,255); run("Convert to Mask");
	if (isOpen("__tmp_or__")) { selectWindow("__tmp_or__"); close(); }
	return ul;
}

// (reverted) matched droplet helper removed
