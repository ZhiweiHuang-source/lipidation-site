"""Generate panel images comparing original and refined masks.

For each base name (image) having original IDP1/IDP2 masks (pattern __mask_IDP1.png / __mask_IDP2.png) and
refined masks (pattern __IDP1_refined.png / __IDP2_refined.png) a 2x2 panel PNG is created:

 Top-Left:  Original IDP1 mask
 Top-Right: Refined IDP1 mask
 Bottom-Left: Original IDP2 mask
 Bottom-Right: Refined IDP2 mask

Additionally a combined mosaic (vertical stack of all panels) is written if --combined-out is provided
or by default as all_masks_panel.png in --out-dir.

No matplotlib required; uses Pillow only.
"""
from __future__ import annotations
import os
import re
import argparse
from typing import Dict
from PIL import Image, ImageDraw, ImageFont

MASK_IDP1_SUFFIX = "__mask_IDP1.png"
MASK_IDP2_SUFFIX = "__mask_IDP2.png"
REF_IDP1_SUFFIX = "__IDP1_refined.png"
REF_IDP2_SUFFIX = "__IDP2_refined.png"


def collect_pairs(mask_dir: str, refined_dir: str):
    pairs: Dict[str, dict] = {}
    # Original masks
    for f in os.listdir(mask_dir):
        if not f.lower().endswith('.png') or '__mask_IDP' not in f:
            continue
        base = re.sub(r"__mask_IDP[12]\.png$", "", f)
        d = pairs.setdefault(base, {})
        if f.endswith(MASK_IDP1_SUFFIX):
            d['orig_idp1'] = os.path.join(mask_dir, f)
        elif f.endswith(MASK_IDP2_SUFFIX):
            d['orig_idp2'] = os.path.join(mask_dir, f)
    # Refined masks
    if os.path.isdir(refined_dir):
        for f in os.listdir(refined_dir):
            if f.endswith(REF_IDP1_SUFFIX):
                base = f[:-len(REF_IDP1_SUFFIX)]
                d = pairs.setdefault(base, {})
                d['ref_idp1'] = os.path.join(refined_dir, f)
            elif f.endswith(REF_IDP2_SUFFIX):
                base = f[:-len(REF_IDP2_SUFFIX)]
                d = pairs.setdefault(base, {})
                d['ref_idp2'] = os.path.join(refined_dir, f)
    return pairs


def load_mask(path: str):
    im = Image.open(path).convert('L')
    return im


def ensure_same_size(images):
    # Resize all to size of first
    if not images:
        return images
    w, h = images[0].size
    out = []
    for im in images:
        if im.size != (w, h):
            im = im.resize((w, h), Image.NEAREST)
        out.append(im)
    return out


def label_image(im: Image.Image, text: str):
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.rectangle([(0,0),(im.width,12)], fill=0)
    draw.text((2,0), text, fill=255, font=font)
    return im


def make_panel(entry: dict, base: str):
    # Return panel Image or None if incomplete
    required = ['orig_idp1','orig_idp2','ref_idp1','ref_idp2']
    if not all(k in entry for k in required):
        return None
    ims = [load_mask(entry[k]) for k in required]
    ims = ensure_same_size(ims)
    labels = ['Orig IDP1','Ref IDP1','Orig IDP2','Ref IDP2']
    labeled = []
    for im, lab in zip(ims, labels):
        labeled.append(label_image(im.copy(), lab))
    w, h = labeled[0].size
    panel = Image.new('L', (w*2, h*2), 0)
    panel.paste(labeled[0], (0,0))
    panel.paste(labeled[1], (w,0))
    panel.paste(labeled[2], (0,h))
    panel.paste(labeled[3], (w,h))
    # Title bar across top
    draw = ImageDraw.Draw(panel)
    title = base
    draw.rectangle([(0,0),(panel.width,14)], fill=128)
    draw.text((4,0), title, fill=255)
    return panel


def build_mosaic(panels):
    if not panels:
        return None
    widths = [p.width for p in panels]
    max_w = max(widths)
    total_h = sum(p.height for p in panels)
    mosaic = Image.new('L', (max_w, total_h), 0)
    y = 0
    for p in panels:
        if p.width < max_w:
            # center horizontally
            x = (max_w - p.width)//2
        else:
            x = 0
        mosaic.paste(p, (x, y))
        y += p.height
    return mosaic


def main():
    ap = argparse.ArgumentParser(description='Generate 2x2 panel PNGs for original vs refined masks.')
    ap.add_argument('--mask-dir', required=True, help='Directory with original mask PNGs')
    ap.add_argument('--refined-dir', required=True, help='Directory with refined mask PNGs')
    ap.add_argument('--out-dir', default='mask_panels', help='Output directory for per-base panels')
    ap.add_argument('--combined-out', default=None, help='Optional single combined mosaic output path')
    args = ap.parse_args()

    pairs = collect_pairs(args.mask_dir, args.refined_dir)
    if not pairs:
        raise SystemExit('No matching masks found.')
    os.makedirs(args.out_dir, exist_ok=True)

    panels = []
    count = 0
    incomplete = 0
    for base, entry in sorted(pairs.items()):
        panel = make_panel(entry, base)
        if panel is None:
            incomplete += 1
            continue
        out_path = os.path.join(args.out_dir, f'{base}_mask_panel.png')
        panel.save(out_path)
        panels.append(panel)
        count += 1
    print(f'Wrote {count} panels. Skipped {incomplete} bases missing refined or original masks.')

    if panels:
        combined_path = args.combined_out
        if combined_path is None:
            combined_path = os.path.join(args.out_dir, 'all_masks_panel.png')
        mosaic = build_mosaic(panels)
        if mosaic:
            mosaic.save(combined_path)
            print(f'Combined mosaic written to {combined_path}')

if __name__ == '__main__':
    main()
