import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
from matplotlib import cm

FIBER_CHANNEL = 1
TDT_CHANNEL = 0
Z_STEP_UM = 1.0
XY_PIXEL_UM = 0.10977
Z_START = 1
Z_END = 30
DOWNSAMPLE_XY = 1

GAUSSIAN_BLUR = True
BLUR_SIGMA_XY_UM = 0.05
BLUR_SIGMA_Z_UM = 0

ELP_MIN = None
ELP_MAX = None
BG_PCT = 91
HI_PCT = 99.9
MASK_THRESH = 0.15
BRIGHTNESS = 1.0
DEPTH_CMAP = "turbo"
INVERT_DEPTH = True
DEPTH_MIN_UM = None
DEPTH_MAX_UM = None

TDT_MIN = None
TDT_MAX = None
TDT_LO_PCT = 50
TDT_HI_PCT = 99.0
TDT_FLOOR = 0.20
TDT_BRIGHT = 1.6
TDT_OPACITY = 0.9
CELL_COLOR = (1.0, 1.0, 1.0)

SCALEBAR_UM = 20

if len(sys.argv) > 1:
    path = sys.argv[1]
else:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Select a .czi or .tif file",
        filetypes=[("Image files", "*.czi *.tif *.tiff"), ("All files", "*.*")])
    root.destroy()
if not path or not os.path.exists(path):
    raise SystemExit("No file selected.")
path = os.path.abspath(path)
stem = os.path.splitext(os.path.basename(path))[0]
OUT_DIR = os.path.join(os.path.dirname(path), stem)
os.makedirs(OUT_DIR, exist_ok=True)

ext = os.path.splitext(path)[1].lower()
if ext == ".czi":
    from aicsimageio import AICSImage
    from aicspylibczi import CziFile
    img = AICSImage(path); czi = CziFile(path)
    order = img.dims.order
    nchan = img.dims.C if "C" in order else 1
    nz = img.dims.Z if "Z" in order else 1
    nt = img.dims.T if "T" in order else 1
    dim_is_z = nz >= nt
    n_stack = nz if dim_is_z else nt
    pps = img.physical_pixel_sizes
    pz = pps.Z or Z_STEP_UM
    px = pps.X or XY_PIXEL_UM

    def read_one(ch, i):
        arr, _ = (czi.read_image(C=ch, Z=i) if dim_is_z else czi.read_image(C=ch, T=i))
        return np.squeeze(np.asarray(arr))
elif ext in (".tif", ".tiff"):
    import tifffile
    tf = tifffile.TiffFile(path)
    ij = tf.imagej_metadata or {}
    npages = len(tf.pages)
    nchan = int(ij.get("channels", 1))
    n_stack = int(ij.get("slices", npages // max(nchan, 1)))
    pz = float(ij.get("spacing", Z_STEP_UM)) or Z_STEP_UM
    try:
        xr = tf.pages[0].tags["XResolution"].value
        px = (xr[1] / xr[0]) if xr[0] else XY_PIXEL_UM
    except Exception:
        px = XY_PIXEL_UM

    def read_one(ch, i):
        return np.asarray(tf.pages[i * nchan + ch].asarray())
else:
    raise SystemExit(f"Unsupported file type '{ext}'.")

def load_stack(ch):
    step = max(1, DOWNSAMPLE_XY)
    planes, ref_shape, missing = [], None, []
    for i in range(n_stack):
        try:
            p = read_one(ch, i).astype(np.float32)[::step, ::step]
            if ref_shape is None:
                ref_shape = p.shape
            planes.append(p)
        except Exception:
            planes.append(None); missing.append(i)
    for i in missing:
        planes[i] = np.zeros(ref_shape, np.float32)
    return np.stack(planes, axis=0)

def stretch(a, manual_lo, manual_hi, lo_pct, hi_pct):
    lo = manual_lo if manual_lo is not None else np.percentile(a, lo_pct)
    hi = manual_hi if manual_hi is not None else np.percentile(a, hi_pct)
    return np.clip((a - lo) / (hi - lo + 1e-9), 0, 1)

fib_vol = load_stack(FIBER_CHANNEL)
tdt_vol = load_stack(TDT_CHANNEL)
if DOWNSAMPLE_XY > 1:
    px *= DOWNSAMPLE_XY

z0 = max(0, int(Z_START))
z1 = fib_vol.shape[0] if Z_END is None else min(int(Z_END), fib_vol.shape[0])
fib_vol = fib_vol[z0:z1]; tdt_vol = tdt_vol[z0:z1]
Z, H, W = fib_vol.shape

if GAUSSIAN_BLUR:
    from scipy import ndimage as ndi
    sz = max(0.0, BLUR_SIGMA_Z_UM / max(pz, 1e-9))
    sxy = max(0.0, BLUR_SIGMA_XY_UM / max(px, 1e-9))
    fib_vol = ndi.gaussian_filter(fib_vol, sigma=(sz, sxy, sxy))
    tdt_vol = ndi.gaussian_filter(tdt_vol, sigma=(sz, sxy, sxy))

fnorm = stretch(fib_vol, ELP_MIN, ELP_MAX, BG_PCT, HI_PCT)
zidx = np.argmax(fnorm, axis=0)
imax = np.max(fnorm, axis=0)
imax[imax < MASK_THRESH] = 0
imax = np.clip(imax * BRIGHTNESS, 0, 1)
if DEPTH_MAX_UM is not None:
    depth_um = z0 * pz + zidx * pz
    dfrac = np.clip((depth_um - DEPTH_MIN_UM) / (DEPTH_MAX_UM - DEPTH_MIN_UM + 1e-9), 0, 1)
else:
    dfrac = zidx / max(Z - 1, 1)

cmap_name = DEPTH_CMAP + ("_r" if INVERT_DEPTH else "")
try:
    cmap = matplotlib.colormaps[cmap_name]
except Exception:
    cmap = cm.get_cmap(cmap_name)
tag = DEPTH_CMAP + ("_inv" if INVERT_DEPTH else "")
rgb = cmap(dfrac)[..., :3] * imax[..., None]

cell = stretch(tdt_vol.max(axis=0), TDT_MIN, TDT_MAX, TDT_LO_PCT, TDT_HI_PCT)
cell = np.clip((cell - TDT_FLOOR) / (1 - TDT_FLOOR + 1e-9), 0, 1)
cell_disp = np.power(cell, 1.0 / max(TDT_BRIGHT, 1e-6))
alpha = (cell_disp * TDT_OPACITY)[..., None]
white = np.array(CELL_COLOR, np.float32)[None, None, :]

def save(arr8, name, with_bar):
    if with_bar:
        arr8 = arr8.copy()
        bar_len = max(1, int(round(SCALEBAR_UM / px)))
        th = max(2, int(round(H * 0.008)))
        x1 = int(W * 0.95); x0 = max(0, x1 - bar_len)
        y1 = int(H * 0.94); y0 = max(0, y1 - th)
        arr8[y0:y1, x0:x1] = 255
    p = os.path.join(OUT_DIR, name)
    mpimg.imsave(p, arr8)
    print("Saved:", p)

tdt_panel = np.repeat((cell_disp * TDT_OPACITY)[..., None], 3, axis=2)
save((np.clip(tdt_panel, 0, 1) * 255).astype(np.uint8), f"{stem}_panel_tdTomato.png", False)
save((np.clip(rgb, 0, 1) * 255).astype(np.uint8), f"{stem}_panel_ELP_depth_{tag}.png", False)
merge = (np.clip(rgb * (1 - alpha) + white * alpha, 0, 1) * 255).astype(np.uint8)
save(merge, f"{stem}_panel_merge_depth_{tag}_nobar.png", False)
save(merge, f"{stem}_panel_merge_depth_{tag}.png", True)
