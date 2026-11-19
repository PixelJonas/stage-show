#!/usr/bin/env python3
"""Prepare images for a stage show. Needs Pillow: run it through the skill's run, after
the skill's install (README, Install).

usage:
  images.py logos IN_DIR OUT_DIR [--box 250x125]
      Trim each logo's empty border, fit it centred into a transparent box of
      the same size for every logo, save as lossless WebP (pixel-checked:
      every visible pixel keeps its colour and alpha). SVGs are copied
      unchanged (vector beats raster). Files sharing a name (acme.svg +
      acme.png, a.jpg + a.png; case-insensitive) give one logo: the SVG,
      else the raster with the most pixels; the others are skipped with a
      WARNING. Writes OUT_DIR/logos.json: [{"name", "src"}] sorted by name.
      "src" is the file's path from the current folder, so run this from the
      show's folder with OUT_DIR inside assets/ (assets/logos): the paths are
      then the literals show.html uses ("assets/logos/acme.webp"). Paste the
      list into the SHOW script as it is; build.py inlines every "src". Edit
      the names to the sponsors' official spelling. IN_DIR and OUT_DIR must
      be different folders (writes nothing otherwise). Images already in
      OUT_DIR that this run did not write (acme.webp from before acme.svg
      arrived, a dropped sponsor) are kept and named in a WARNING.
  images.py photos FILE... OUT_DIR [--max 1600] [--quality 82]
      Apply EXIF rotation, downscale to the longest edge, save as WebP.
      Refuses (writes nothing) when two files share a name (a.jpg + a.png)
      or a file would be overwritten by its own output (OUT_DIR/a.webp).
  images.py masks PDF MEDIA_DIR
      `pdfimages -png -p PDF MEDIA_DIR/pdf` writes a soft mask (the rows
      `pdfimages -list` marks smask) as its own grey picture, so a transparent
      logo or icon shows as a black box. This puts each mask back on its
      picture as alpha (MEDIA_DIR/pdf-PPP-NNN.png, rewritten in place).
  images.py sheet FILE... OUT.png [--cols 4] [--cell 384]
      Contact sheets: the files in a grid of 16:9 cells, each labelled with
      its file name, cols x cols cells a sheet (OUT-1.png, OUT-2.png, ...
      when more). For an overview only: open a file at full size wherever
      its cell is too small to judge.
"""
import argparse, io, json, os, shutil, subprocess, sys
try:
    from PIL import Image, ImageChops, ImageOps
except ImportError:
    skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(f"Pillow missing: run \"{skill}/install\", then this script through {skill}/run; or, without mise, pip install -r {skill}/requirements.txt (README, Install)")

RASTER = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")


def trim(im):
    im = im.convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box and box != (0, 0, *im.size):
        return im.crop(box)
    # opaque logo: trim a near-white border instead
    rgb = im.convert("RGB")
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255))).convert("L").point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    return im.crop(box) if box else im


def visible(im):
    """RGBA bytes with fully transparent pixels zeroed: what the logo shows on any background."""
    im = im.convert("RGBA")  # a copy, so the caller's image stays untouched
    im.paste((0, 0, 0, 0), mask=im.getchannel("A").point(lambda a: 255 if a == 0 else 0))
    return im.tobytes()


def preference(src, fn):
    """Sort key among files sharing a logo name: SVG first, then the raster with the most pixels, then file name."""
    if fn.lower().endswith(".svg"):
        return (0, 0, fn)
    with Image.open(os.path.join(src, fn)) as im:
        return (1, -im.width * im.height, fn)


def literal(out, fn):
    """OUT_DIR/fn as show.html writes it: relative to the current folder, with forward slashes."""
    return os.path.relpath(os.path.join(out, fn)).replace(os.sep, "/")


def logos(src, out, w, h):
    if os.path.isdir(src) and os.path.isdir(out) and os.path.samefile(src, out):
        sys.exit(f"nothing written: IN_DIR and OUT_DIR are the same folder ({out}), so the results would overwrite the originals.\n"
                 "Keep the originals in their own folder (e.g. source/logos) and write to assets/logos.")
    os.makedirs(out, exist_ok=True)
    files = sorted(os.listdir(src))
    groups = {}  # casefolded stem -> input files that would become the same logo
    for fn in files:
        stem, ext = os.path.splitext(fn)
        if ext.lower() == ".svg" or ext.lower() in RASTER:
            groups.setdefault(stem.casefold(), []).append(fn)
    keep = {k: min(g, key=lambda fn: preference(src, fn)) if len(g) > 1 else g[0] for k, g in groups.items()}
    res = []
    for fn in files:
        stem, ext = os.path.splitext(fn)
        p = os.path.join(src, fn)
        if ext.lower() != ".svg" and ext.lower() not in RASTER:
            print(f"{fn:40} skipped (not an image)")
            continue
        if keep[stem.casefold()] != fn:
            print(f"{fn:40} skipped (same name as {keep[stem.casefold()]}, which is kept)")
            continue
        if ext.lower() == ".svg":
            shutil.copyfile(p, os.path.join(out, fn))
            res.append({"name": stem, "src": literal(out, fn)})
            print(f"{fn:40} svg, copied")
            continue
        im = trim(Image.open(p))
        f = min(w / im.width, h / im.height)
        small = f > 1.5
        im = im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))), Image.LANCZOS)
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        x, y = (w - im.width) // 2, (h - im.height) // 2
        canvas.paste(im, (x, y))  # no mask: the canvas is empty, so colour and alpha are copied unchanged
        b = io.BytesIO()
        canvas.save(b, "WEBP", lossless=True, quality=100, method=6)
        # the file shows every visible pixel of the fitted logo unchanged, alpha included
        assert canvas.crop((x, y, x + im.width, y + im.height)).tobytes() == im.tobytes(), fn
        assert visible(Image.open(io.BytesIO(b.getvalue()))) == visible(canvas), fn
        name = stem + ".webp"
        open(os.path.join(out, name), "wb").write(b.getvalue())
        res.append({"name": stem, "src": literal(out, name)})
        print(f"{fn:40} {Image.open(p).size} -> {w}x{h} webp {len(b.getvalue()):,} B" + ("  (upscaled: ask for a bigger or vector logo)" if small else ""))
    res.sort(key=lambda x: x["name"].casefold())
    json.dump(res, open(os.path.join(out, "logos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(res)} logos, list in {os.path.join(out, 'logos.json')}")
    if any(not r["src"].startswith("assets/") for r in res):
        print("WARNING: the paths in logos.json don't start with assets/, so build.py won't inline them; "
              "run images.py from the show's folder with OUT_DIR inside assets/ (e.g. assets/logos)", file=sys.stderr)
    sys.stdout.flush()
    written = {os.path.basename(r["src"]) for r in res}
    stale = sorted(fn for fn in os.listdir(out) if fn not in written and os.path.isfile(os.path.join(out, fn))
                   and (os.path.splitext(fn)[1].lower() == ".svg" or os.path.splitext(fn)[1].lower() in RASTER))
    if stale:
        print(f"WARNING: this run did not write {', '.join(literal(out, fn) for fn in stale)}, and logos.json doesn't list "
              "them (left from an earlier run, or placed by hand). Delete them unless show.html uses them.", file=sys.stderr)
    for k, g in sorted(groups.items()):
        if len(g) > 1:
            lost = ", ".join(fn for fn in g if fn != keep[k])
            print(f"WARNING: {lost} skipped: same logo name as {keep[k]}, which is kept. Delete or rename the file you don't want.", file=sys.stderr)


def photos(files, out, mx, q):
    groups = {}  # each photo becomes <stem>.webp: same stems (case-insensitive) would overwrite each other
    for p in files:
        groups.setdefault(os.path.splitext(os.path.basename(p))[0].casefold(), []).append(p)
    clash = [g for g in groups.values() if len(g) > 1]
    if clash:
        sys.exit("nothing written; these photos would get the same output name, rename all but one:\n"
                 + "\n".join("  " + " + ".join(g) for g in clash))
    target = lambda p: os.path.join(out, os.path.splitext(os.path.basename(p))[0] + ".webp")
    own = [p for p in files if os.path.exists(target(p)) and os.path.samefile(p, target(p))]
    if own:
        sys.exit("nothing written; these photos would be overwritten by their own output, write to another folder:\n"
                 + "\n".join("  " + p for p in own))
    os.makedirs(out, exist_ok=True)
    for p in files:
        im = ImageOps.exif_transpose(Image.open(p))
        im.thumbnail((mx, mx), Image.LANCZOS)
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA" if has_alpha else "RGB")
        name = os.path.splitext(os.path.basename(p))[0] + ".webp"
        im.save(os.path.join(out, name), "WEBP", quality=q, method=6)
        print(f"{os.path.basename(p):40} {os.path.getsize(p):>10,} B -> {name} {im.size} {os.path.getsize(os.path.join(out, name)):,} B")


def masks(pdf, media):
    rows = subprocess.run(["pdfimages", "-list", pdf], capture_output=True, text=True, check=True).stdout.splitlines()[2:]
    base, n = None, 0
    for row in rows:  # each smask row follows the row of its picture
        f = row.split()
        if len(f) < 3 or not f[0].isdigit():
            continue
        p = os.path.join(media, f"pdf-{int(f[0]):03d}-{int(f[1]):03d}.png")
        if f[2] == "image":
            base = p
        elif f[2] == "smask" and base and os.path.exists(base) and os.path.exists(p):
            with Image.open(base) as im, Image.open(p) as m:
                im = im.convert("RGBA")
                im.putalpha(m.convert("L").resize(im.size, Image.LANCZOS))
            im.save(base)
            n += 1
            print(f"{os.path.basename(base):40} alpha from {os.path.basename(p)}")
    print(f"{n} pictures got their soft mask")


def sheet(files, out, cols, cell):
    from PIL import ImageDraw, ImageFont
    w, h, lab = cell, cell * 9 // 16, 24
    font, per, (stem, ext) = ImageFont.load_default(size=16), cols * cols, os.path.splitext(out)
    if any(os.path.abspath(p) == os.path.abspath(out) for p in files):
        sys.exit(f"nothing written: {out} is one of the inputs")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    pages = [files[i:i + per] for i in range(0, len(files), per)]
    for k, page in enumerate(pages, 1):
        im = Image.new("RGB", (cols * w, -(-len(page) // cols) * (h + lab)), (64, 64, 64))
        d = ImageDraw.Draw(im)
        for i, p in enumerate(page):
            x, y = i % cols * w, i // cols * (h + lab)
            with Image.open(p) as t:
                t = ImageOps.exif_transpose(t).convert("RGB")
                t.thumbnail((w - 4, h - 4), Image.LANCZOS)
                im.paste(t, (x + (w - t.width) // 2, y + (h - t.height) // 2))
            d.text((x + 4, y + h + 2), os.path.basename(p)[:w // 9], fill="white", font=font)
        name = out if len(pages) == 1 else f"{stem}-{k}{ext}"
        im.save(name)
        print(f"{name}: {len(page)} of {len(files)} files")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("cmd", choices=["logos", "photos", "masks", "sheet"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--box", default="250x125")
    ap.add_argument("--max", type=int, default=1600)
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--cell", type=int, default=384)
    a = ap.parse_args()
    if a.cmd in ("logos", "masks") and len(a.paths) != 2 or len(a.paths) < 2:
        sys.exit(__doc__)
    if a.cmd == "masks":
        masks(*a.paths)
    elif a.cmd == "sheet":
        sheet(a.paths[:-1], a.paths[-1], a.cols, a.cell)
    elif a.cmd == "logos":
        bw, bh = map(int, a.box.lower().split("x"))
        logos(a.paths[0], a.paths[1], bw, bh)
    else:
        photos(a.paths[:-1], a.paths[-1], a.max, a.quality)
