#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zoom_crop.py — crop + magnify a region of a photo so small text becomes readable.

Motivated by a classic mistake: the `read` tool reports a photo as
"original 4096x3072, displayed at 2000x1500. Multiply coordinates by 2.05",
and a rectangle measured on the *displayed* image must be multiplied by that
factor before cropping, otherwise you crop the ceiling.

Usage (original-image pixel coordinates):
    python3 zoom_crop.py photo.jpg out.png --box 300,890,3350,1900 --zoom 2 --gray --enhance

Usage (coordinates measured on the displayed/preview image — the script applies the factor):
    python3 zoom_crop.py photo.jpg out.png --display-box 150,340,1620,900 \
        --display-size 2000x1500 --zoom 2 --gray --enhance

Options
    --box X1,Y1,X2,Y2     crop rectangle in ORIGINAL image pixels (inclusive-exclusive)
    --display-box ...     crop rectangle in displayed-preview pixels
    --display-size WxH    size the picture was displayed at (from the read tool output)
    --zoom N              integer upscale factor (default 2), uses LANCZOS
    --gray                convert to grayscale (a projector photo is often easier
                          to read this way, and JPEG chroma noise disappears)
    --enhance             autocontrast + unsharp mask (mild sharpening)
    --rotate DEG          rotate after cropping (use for tilted screenshots)
    --grid                draw a 10x10 coordinate grid with the original-pixel
                          ruler on the edges, to locate cells precisely
    --out-scale K         also print the box converted to original pixels

Always print the resulting image size so the caller knows what it got.
Prints the equivalent original-pixel box, which is what you want to record.
"""

import argparse
import sys

from PIL import Image, ImageFilter, ImageOps, ImageDraw


def parse_box(s):
    parts = [float(p) for p in s.replace(' ', '').split(',')]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError('box must be X1,Y1,X2,Y2')
    return parts


def parse_size(s):
    w, h = s.lower().replace(' ', '').split('x')
    return float(w), float(h)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('image')
    ap.add_argument('out')
    ap.add_argument('--box', type=parse_box)
    ap.add_argument('--display-box', type=parse_box)
    ap.add_argument('--display-size', type=parse_size)
    ap.add_argument('--zoom', type=float, default=2)
    ap.add_argument('--gray', action='store_true')
    ap.add_argument('--enhance', action='store_true')
    ap.add_argument('--rotate', type=float, default=0.0)
    ap.add_argument('--grid', action='store_true')
    args = ap.parse_args(argv)

    im = Image.open(args.image)
    W, H = im.size
    print('original image: %dx%d' % (W, H))

    if args.display_box:
        if not args.display_size:
            ap.error('--display-box requires --display-size WxH')
        dw, dh = args.display_size
        fx, fy = W / dw, H / dh
        box = [args.display_box[0] * fx, args.display_box[1] * fy,
               args.display_box[2] * fx, args.display_box[3] * fy]
        print('displayed %gx%g -> factor %gx%g' % (dw, dh, fx, fy))
    elif args.box:
        box = args.box
    else:
        ap.error('one of --box / --display-box is required')

    box = [max(0, min(W, box[0])), max(0, min(H, box[1])),
           max(0, min(W, box[2])), max(0, min(H, box[3]))]
    if box[2] <= box[0] or box[3] <= box[1]:
        ap.error('empty crop box after clamping: %s' % box)
    print('crop box in original pixels: %d,%d,%d,%d' % tuple(int(v) for v in box))

    crop = im.crop(tuple(int(round(v)) for v in box))
    if args.rotate:
        crop = crop.rotate(args.rotate, resample=Image.BICUBIC, expand=True)
    if args.zoom and args.zoom != 1:
        crop = crop.resize((max(1, int(crop.width * args.zoom)),
                            max(1, int(crop.height * args.zoom))), Image.LANCZOS)
    if args.gray:
        crop = crop.convert('L')
    if args.enhance:
        crop = ImageOps.autocontrast(crop, cutoff=0)
        crop = crop.filter(ImageFilter.UnsharpMask(radius=3, percent=160, threshold=2))
    if args.grid:
        crop = crop.convert('RGB')
        d = ImageDraw.Draw(crop)
        step_x = max(1, crop.width // 10)
        step_y = max(1, crop.height // 10)
        for i in range(11):
            x = min(crop.width - 1, i * step_x)
            y = min(crop.height - 1, i * step_y)
            d.line([(x, 0), (x, crop.height)], fill=(255, 0, 0), width=1)
            d.line([(0, y), (crop.width, y)], fill=(255, 0, 0), width=1)
            ox = int(box[0] + (box[2] - box[0]) * i / 10)
            oy = int(box[1] + (box[3] - box[1]) * i / 10)
            d.text((x + 2, 2), str(ox), fill=(255, 0, 0))
            d.text((2, y + 2), str(oy), fill=(255, 0, 0))

    crop.save(args.out)
    print('saved %s  %dx%d' % (args.out, crop.width, crop.height))
    print('TIP: crop again tighter with --box using the printed original-pixel ruler.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
