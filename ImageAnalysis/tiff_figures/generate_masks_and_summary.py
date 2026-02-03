"""Generate IDP1/IDP2 masks from OME-TIFF images and produce a summary CSV.

For every .ome.tif in --image-dir (default ./other) this script:
 1. Extracts 2D planes for the specified channels (default ch1=0, ch2=1) using T=0, max Z projection.
 2. Applies Otsu threshold per channel to create binary masks (IDP1 from ch1, IDP2 from ch2).
 3. (Optional) Erodes masks by --erode-px.
 4. Saves masks as <basename>__mask_IDP1.png and <basename>__mask_IDP2.png in --mask-dir.
 5. Computes cross-channel means and K1=(C1_in_IDP1)/(C1_in_IDP2), K2=(C2_in_IDP2)/(C2_in_IDP1).
 6. Counts connected components (parts1, parts2).
 7. Writes a CSV with columns mirroring previous k12_unified format.
 8. Appends GROUP_MEAN rows aggregating K1,K2 over replicate sets.

Notes:
 - Channels are zero-based internally; CSV stores 1-based (matching prior file ch1=1, ch2=2).
 - Background subtraction not performed (sub_bg=0) to stay consistent with provided example.
 - Grouping heuristic: remove trailing _[1-9]_Composite_T0 or _Composite_T0 to obtain group label.

"""
from __future__ import annotations
import os, re, time, argparse
from typing import Tuple, Dict, List
import numpy as np
from PIL import Image

try:
    import tifffile
except ImportError:
    raise SystemExit("Missing tifffile. Install with: pip install tifffile")

# ---------------- Image loading helpers ---------------- #

def _find_axes_and_array(tf: 'tifffile.TiffFile') -> Tuple[str, np.ndarray]:
    series = tf.series[0]
    axes = getattr(series, 'axes', None)
    arr = series.asarray()
    if axes is None:
        if arr.ndim == 2:
            axes = 'YX'
        elif arr.ndim == 3:
            axes = 'CYX' if arr.shape[0] <= 4 else 'ZYX'
        elif arr.ndim == 4:
            axes = 'CZYX'
        elif arr.ndim == 5:
            axes = 'TCZYX'
        else:
            raise RuntimeError(f'Unrecognized image dims {arr.shape}')
    return axes, arr

def extract_plane(img_path: str, channel: int=0) -> np.ndarray:
    with tifffile.TiffFile(img_path) as tf:
        axes, arr = _find_axes_and_array(tf)
    arr = arr.astype(np.float32, copy=False)
    # Channel select
    if 'C' in axes:
        cidx = axes.index('C')
        if channel >= arr.shape[cidx]:
            raise IndexError(f'Channel {channel} out of range for shape {arr.shape} axes {axes}')
        arr = np.take(arr, indices=channel, axis=cidx)
        axes = axes.replace('C','',1)
    # Time
    if 'T' in axes:
        tidx = axes.index('T')
        arr = np.take(arr, indices=0, axis=tidx)
        axes = axes.replace('T','',1)
    # Max project Z
    if 'Z' in axes:
        zidx = axes.index('Z')
        arr = np.max(arr, axis=zidx)
        axes = axes.replace('Z','',1)
    if arr.ndim != 2:
        arr = np.squeeze(arr)
    if arr.ndim != 2:
        raise RuntimeError('Failed to reduce to 2D plane')
    return arr

# ---------------- Thresholding / segmentation ---------------- #

def otsu_threshold(a: np.ndarray) -> float:
    # Compute on finite values
    a = a[np.isfinite(a)]
    if a.size == 0:
        return 0.0
    # Scale to 256 bins
    mn, mx = float(a.min()), float(a.max())
    if mx <= mn:
        return mn
    hist, edges = np.histogram(a, bins=256, range=(mn, mx))
    hist = hist.astype(float)
    prob = hist / hist.sum()
    omega = np.cumsum(prob)
    mu = np.cumsum(prob * (edges[:-1] + np.diff(edges)/2.0))
    mu_t = mu[-1]
    sigma_b2 = (mu_t * omega - mu)**2 / (omega * (1-omega) + 1e-12)
    idx = np.nanargmax(sigma_b2)
    return (edges[idx] + edges[idx+1]) / 2.0

try:
    from scipy.ndimage import binary_erosion, label as cc_label
    def erode(mask: np.ndarray, n: int) -> np.ndarray:
        if n<=0: return mask
        m = mask.copy()
        for _ in range(n):
            m = binary_erosion(m)
            if not m.any():
                break
        return m
    def count_components(mask: np.ndarray) -> int:
        if not mask.any():
            return 0
        lbl, num = cc_label(mask)
        return int(num)
except Exception:
    # Fallback pure Python connected component counting (4-neighborhood)
    def erode(mask: np.ndarray, n: int) -> np.ndarray:
        return mask if n<=0 else mask  # no-op
    def count_components(mask: np.ndarray) -> int:
        if not mask.any(): return 0
        visited = np.zeros(mask.shape, bool)
        h, w = mask.shape
        comps = 0
        for y in range(h):
            for x in range(w):
                if mask[y,x] and not visited[y,x]:
                    comps += 1
                    stack=[(y,x)]
                    visited[y,x]=True
                    while stack:
                        cy,cx=stack.pop()
                        for ny,nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                            if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not visited[ny,nx]:
                                visited[ny,nx]=True
                                stack.append((ny,nx))
        return comps

# ---------------- Grouping ---------------- #

def group_label(basename: str) -> str:
    # Remove extension already stripped. Pattern *_<digit>_Composite_T0 or *_Composite_T0
    s = re.sub(r'_[0-9]+_Composite_T0$', '_Composite_T0', basename)
    label = re.sub(r'_Composite_T0$', '', s)
    return label

# ---------------- Main processing ---------------- #

def process_image(path: str, ch1: int, ch2: int, erode_px: int) -> Dict[str, object]:
    base = os.path.basename(path).rsplit('.ome.tif',1)[0]
    img1 = extract_plane(path, channel=ch1)
    img2 = extract_plane(path, channel=ch2)
    thr1 = otsu_threshold(img1)
    thr2 = otsu_threshold(img2)
    m1 = img1 > thr1
    m2 = img2 > thr2
    if erode_px>0:
        m1 = erode(m1, erode_px)
        m2 = erode(m2, erode_px)
    # Ensure non-empty fallback: keep top 0.5% brightest if empty
    if not m1.any():
        t = np.percentile(img1, 99.5)
        m1 = img1 >= t
    if not m2.any():
        t = np.percentile(img2, 99.5)
        m2 = img2 >= t
    # Metrics
    c1_roi1 = float(img1[m1].mean()) if m1.any() else float('nan')
    c1_den  = float(img1[m2].mean()) if m2.any() else float('nan')
    c2_roi2 = float(img2[m2].mean()) if m2.any() else float('nan')
    c2_den  = float(img2[m1].mean()) if m1.any() else float('nan')
    k1 = (c1_roi1 / c1_den) if (c1_den and c1_den>0) else float('nan')
    k2 = (c2_roi2 / c2_den) if (c2_den and c2_den>0) else float('nan')
    return {
        'base': base,
        'mask1': m1,
        'mask2': m2,
        'mean_C1_ROI1': c1_roi1,
        'mean_C1_den': c1_den,
        'mean_C2_ROI2': c2_roi2,
        'mean_C2_den': c2_den,
        'K1': k1,
        'K2': k2,
        'area1': int(m1.sum()),
        'area2': int(m2.sum()),
        'parts1': count_components(m1),
        'parts2': count_components(m2),
        'thr1': thr1,
        'thr2': thr2,
    }

# ---------------- CSV writing ---------------- #

def write_csv(rows: List[Dict[str,object]], out_path: str, ch1: int, ch2: int):
    import csv
    fieldnames = [
        'filename','image_rel','ch1','ch2','mean_C1_ROI1','mean_C1_den','mean_C2_ROI2','mean_C2_den','K1','K2',
        'area_ROI1_px','area_ROI2_px','parts1','parts2','th1','th2','obj1_bright','obj2_bright','thr_on_8bit',
        'th1_off','th2_off','th1_man','th2_man','open','close','fill','unify','dilate','min_size','exclude_edges',
        'dilute1_mode','dilute2_mode','ring_px','sub_bg','error'
    ]
    groups: Dict[str, List[float]] = {}
    for r in rows:
        glab = group_label(r['filename'])
        groups.setdefault(glab, []).append(r['K1'])  # store K1 for presence check
    with open(out_path,'w',newline='',encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({
                'filename': r['filename'],
                'image_rel': r['image_rel'],
                'ch1': ch1+1,
                'ch2': ch2+1,
                'mean_C1_ROI1': r['mean_C1_ROI1'],
                'mean_C1_den': r['mean_C1_den'],
                'mean_C2_ROI2': r['mean_C2_ROI2'],
                'mean_C2_den': r['mean_C2_den'],
                'K1': r['K1'],
                'K2': r['K2'],
                'area_ROI1_px': r['area1'],
                'area_ROI2_px': r['area2'],
                'parts1': r['parts1'],
                'parts2': r['parts2'],
                'th1': 'Otsu',
                'th2': 'Otsu',
                'obj1_bright': 1,
                'obj2_bright': 1,
                'thr_on_8bit': 1,
                'th1_off': 0,'th2_off':0,'th1_man':0,'th2_man':0,
                'open':0,'close':0,'fill':0,'unify':0,'dilate':0,'min_size':0,'exclude_edges':0,
                'dilute1_mode':'Other IDP mask','dilute2_mode':'Other IDP mask','ring_px':10,'sub_bg':0,'error':'',
            })
        # Group means (K1,K2 average across rows where group label applies)
        group_map: Dict[str, List[Tuple[float,float]]] = {}
        for r in rows:
            glab = group_label(r['filename'])
            group_map.setdefault(glab, []).append((r['K1'], r['K2']))
        for glab, vals in sorted(group_map.items()):
            k1s = [v[0] for v in vals if np.isfinite(v[0])]
            k2s = [v[1] for v in vals if np.isfinite(v[1])]
            if not k1s and not k2s:
                continue
            gk1 = np.mean(k1s) if k1s else ''
            gk2 = np.mean(k2s) if k2s else ''
            w.writerow({'filename': f'GROUP_MEAN:{glab}', 'K1': gk1, 'K2': gk2})
    print(f"Summary written to {out_path} ({len(rows)} images, {len(group_map)} groups)")

# ---------------- CLI ---------------- #

def main():
    ap = argparse.ArgumentParser(description='Generate masks & summary CSV from OME-TIFF images.')
    ap.add_argument('--image-dir', default='other', help='Directory containing input .ome.tif images')
    ap.add_argument('--mask-dir', default='masks', help='Directory to save generated masks')
    ap.add_argument('--out-csv', default=None, help='Output CSV path (default k12_unified_<timestamp>.csv in mask-dir)')
    ap.add_argument('--ch1', type=int, default=0, help='Channel index for IDP1 (0-based)')
    ap.add_argument('--ch2', type=int, default=1, help='Channel index for IDP2 (0-based)')
    ap.add_argument('--erode-px', type=int, default=1, help='Erode masks by N pixels after thresholding (default 1)')
    ap.add_argument('--overwrite', action='store_true', help='Overwrite existing mask PNGs')
    args = ap.parse_args()

    if not os.path.isdir(args.image_dir):
        raise SystemExit(f'Image dir not found: {args.image_dir}')
    os.makedirs(args.mask_dir, exist_ok=True)

    images = [f for f in os.listdir(args.image_dir) if f.endswith('.ome.tif')]
    if not images:
        raise SystemExit('No .ome.tif images found')

    rows = []
    for fname in sorted(images):
        path = os.path.join(args.image_dir, fname)
        base = fname.rsplit('.ome.tif',1)[0]
        try:
            info = process_image(path, args.ch1, args.ch2, args.erode_px)
            # Save masks
            m1_path = os.path.join(args.mask_dir, base + '__mask_IDP1.png')
            m2_path = os.path.join(args.mask_dir, base + '__mask_IDP2.png')
            if args.overwrite or (not os.path.exists(m1_path)):
                Image.fromarray(info['mask1'].astype(np.uint8)*255).save(m1_path)
            if args.overwrite or (not os.path.exists(m2_path)):
                Image.fromarray(info['mask2'].astype(np.uint8)*255).save(m2_path)
            rows.append({
                'filename': base,
                'image_rel': os.path.join(args.image_dir, fname),
                'mean_C1_ROI1': info['mean_C1_ROI1'],
                'mean_C1_den': info['mean_C1_den'],
                'mean_C2_ROI2': info['mean_C2_ROI2'],
                'mean_C2_den': info['mean_C2_den'],
                'K1': info['K1'],
                'K2': info['K2'],
                'area1': info['area1'],
                'area2': info['area2'],
                'parts1': info['parts1'],
                'parts2': info['parts2'],
            })
        except Exception as e:
            print(f'[error] {fname}: {e}')
    ts = int(time.time()*1000)
    out_csv = args.out_csv or os.path.join(args.mask_dir, f'k12_unified_{ts}.csv')
    write_csv(rows, out_csv, args.ch1, args.ch2)

if __name__ == '__main__':
    main()
