# Reading the source

**File names.** Keep the received deck in `source/` under its own name, record that name in content.md, and hard-link the plain name the commands use, `ln "source/<received name>" source/deck.pdf` (or `deck.pptx`), so no command needs quotes. A file already so named needs nothing; a `.key` that is a folder skips this (Keynote, below); where `ln` is refused (FAT, exFAT, some network mounts), copy instead. Unpack archives (`.key`, zips of images) into their own empty folder.

**A revised deck.** Move everything in `source/` except earlier `vN/` folders into `source/v1/` (v2, … later), the received files included: a revision often keeps the old name, and copied over it, the hard-linked plain name in `v1/` takes the new content and a Keynote folder merges. Copy the new deck in, extract it, compare the new extract with the folder you just filled (`deck.md` or `deck.txt`, the contact sheets), and carry every change into content.md.

**OCR.** Text that exists only as pixels needs tesseract: PDF pages without a text layer, slide images, the pictures of a `.key` whose text no export supplies. Run `<skill>/install ocr` before the first `tesseract` command.

| in `source/` | content |
|---|---|
| `deck.md`, `theme.json` | PPTX text, notes, tables, SmartArt, chart data, pictures, video, footer and master text; theme. `[warning]` marks what was unreadable |
| `deck.txt` | PDF text, pages split by form feeds |
| `pages/p-N.png` | overview, 800 px long side: look at every one |
| `read/p-N.png` | reading set, 2000 px (about 150 dpi on a 13.3 in slide): small print, chart labels |
| `media/` | full-size pictures: `sNN-*`, `master-*` (PPTX), `pdf-<page>-<n>.png` (n counts through the file), `key/` (Keynote) |

pdftoppm pads N to the page count's digits (`p-01.png` from 10 pages).

## PPTX

`<skill>/scripts/extract_pptx.py` (SKILL.md step 2) lists footer text and text on masters and layouts once at the end of `deck.md`, with their slides; its `[warning]` lines get checked against the page pictures.

The user's PDF export is the reference rendering. Without one, LibreOffice renders a fallback that may differ: `soffice --headless --convert-to pdf --outdir source/render source/deck.pptx` (macOS: `/Applications/LibreOffice.app/Contents/MacOS/soffice`), then the PDF commands on `source/render/deck.pdf`. PowerPoint drops hidden slides from its PDF unless "Include hidden slides" is ticked; `deck.md` marks them and gives every other slide its PDF page (`pages/p-5.png` may be slide 6). As many pages as slides: page N is slide N.

## PDF

```sh
<skill>/run pdfinfo source/deck.pdf          # page count, page size in pt (aspect = width / height)
<skill>/run pdftotext -layout source/deck.pdf source/deck.txt
<skill>/run python3 -I -c 'import re,sys,unicodedata as u; p=sys.argv[1]; s=open(p,encoding="utf-8").read(); open(p,"w",encoding="utf-8").write(re.sub("[\ufb00-\ufb06]", lambda m: u.normalize("NFKC", m[0]), s))' source/deck.txt   # ligatures (ﬁ, ﬂ) as plain letters
mkdir -p source/pages source/read source/media source/vector source/ocr
<skill>/run pdftoppm -png -scale-to 800 source/deck.pdf source/pages/p
<skill>/run pdftoppm -png -scale-to 2000 source/deck.pdf source/read/p
<skill>/run pdfimages -list source/deck.pdf  # embedded pictures: page, size, ppi
<skill>/run pdfimages -png -p source/deck.pdf source/media/pdf
<skill>/run python3 -I <skill>/scripts/images.py masks source/deck.pdf source/media   # transparency back onto logos and icons
<skill>/run pdfinfo -url source/deck.pdf > source/links.txt   # every link with its page: into content.md
<skill>/run pdffonts source/deck.pdf > source/fonts.txt
```

`-scale-to`, not `-r`: page sizes differ between exporters. `pdfimages` numbers pictures in file order, without positions: match each to its place on the page picture (similar charts swap easily). The ligature line turns U+FB00–FB06 (ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ), which Google Fonts subsets lack, into plain letters, and only that range (NFKC on all text would change ™ and ²); apply it to any text you copy from a PDF. Before poppler 21.11 `pdfinfo` has no `-url`: `<skill>/run pdftohtml -xml -i -stdout source/deck.pdf > source/links.xml` lists links on text, not on pictures.

- **Fonts:** `fonts.txt` names every font (drop the `ABCDEF+` prefix); `emb no` means not even embedded.
- **Pages without a text layer** (scans, flattened exports): `for n in $(seq 1 $(<skill>/run pdfinfo source/deck.pdf | awk '/^Pages:/{print $2}')); do printf "page %s: %s words\n" $n $(<skill>/run pdftotext -f $n -l $n source/deck.pdf - | wc -w); done`. When `pdfimages -list` shows one page-sized picture on such a page, OCR that picture: `<skill>/run tesseract source/media/pdf-003-001.png source/ocr/p-3 -l <lang>`; otherwise render the page first, `<skill>/run pdftoppm -png -r 300 -f 3 -l 3 -singlefile source/deck.pdf source/ocr/p-3`, then `<skill>/run tesseract source/ocr/p-3.png source/ocr/p-3 -l <lang>`. `<lang>` is the deck's language as `<skill>/run tesseract --list-langs` names it: `-l deu` for German reads a mixed slide's English lines too, while `-l eng` turns "Übersicht" into "Ubersicht". A tesseract installed by hand needs that language's pack (`<lang>.traineddata`): ask before installing it. Check every number against the picture: a rendered page can read "37" as "3/7" where the embedded picture reads it right.
- **Colours:** vector shapes carry the exact brand colours; count a page's fill and stroke colours (both cairo forms, `fill="rgb(…)"` and `style="…fill:rgb(…)…"`):
  `<skill>/run pdftocairo -svg -f 1 -l 1 source/deck.pdf source/vector/p-1.svg && grep -ohE '(fill|stroke)[=:]"?rgb\([^)]*\)' source/vector/p-1.svg | <skill>/run python3 -I -c 'import sys,re,collections; print(collections.Counter("#%02X%02X%02X" % tuple(round(float(v) * 2.55) for v in re.findall(r"([\d.]+)%", l)) for l in sys.stdin).most_common(12))'`
  For photos and backgrounds, count pixels:
  `<skill>/run pdftoppm -scale-to 200 -f 1 -l 1 -singlefile source/deck.pdf source/vector/c-1 && <skill>/run python3 -I -c 'import collections,re,sys; d=open(sys.argv[1],"rb").read(); m=re.match(rb"P6\s+(\d+)\s+(\d+)\s+\d+\s",d); px=d[m.end():]; n=int(m[1])*int(m[2]); print([("#"+k, round(100*c/n, 1)) for k,c in collections.Counter(px[i:i+3].hex().upper() for i in range(0,3*n,3)).most_common(6)])' source/vector/c-1.ppm`
- **Transparency:** `pdfimages -png` writes a soft mask (an `smask` row in `-list`) as a separate grey picture, leaving a transparent logo as a black box; the block's `<skill>/scripts/images.py masks` puts each mask back.
- **Material under usage rules** (stagecraft.md, Content): ask for the original file; otherwise take it as the PDF holds it: `mkdir -p source/media/as-supplied && <skill>/run pdfimages -all -f <page> -l <page> -p source/deck.pdf source/media/as-supplied/pdf` writes a JPEG byte for byte, other pictures as PNG with the same pixels; `cp` it into `assets/` and check the build (qa.md). With an `smask` row after it, look at the mask: one that only clears a plain edge (a white column) lets the picture sit on a backing of that colour; anything more, ask for the original. A whole approved slide is rendered from the user's own PDF export or the owner's file, never from a LibreOffice render or a slide image, at twice the stage resolution, lossless: `mkdir -p source/media/as-supplied assets && <skill>/run pdftoppm -png -f <page> -l <page> -scale-to 3840 -singlefile source/deck.pdf source/media/as-supplied/slide-<page> && <skill>/run python3 -I -c 'import sys,PIL.Image as I; I.open(sys.argv[1]).save(sys.argv[2], lossless=True)' source/media/as-supplied/slide-<page>.png assets/slide-<page>.webp`.
- **QR codes:** decode each from its page picture: `<skill>/run python3 -I -c 'import sys,zxingcpp,PIL.Image as I; [print(b.text, "at", b.position) for b in zxingcpp.read_barcodes(I.open(sys.argv[1]))] or sys.exit("no QR code found")' source/read/p-<N>.png` prints each code's address (not from its file in `media/`: under transparency zxing-cpp sees the stored colour, often black). Check it against `links.txt` and the slide text: nothing decoded, take it from those; disagreeing or none, ask the user.
- **Vector logos and charts:** `pdfimages` sees only pictures. Cut a vector logo out: measure its box on the overview picture, multiply by page width in pt / 800, and crop: `<skill>/run pdftocairo -svg -f 1 -l 1 -x 795 -y 45 -W 120 -H 120 source/deck.pdf source/vector/logo.svg`. The SVG keeps the page size and centres the crop, so set its first `viewBox` to `(page width − W)/2 (page height − H)/2 W H`, and its size to W × H: `<skill>/run python3 -I -c 'import re,sys; f,b=sys.argv[1:]; w,h=b.split()[2:]; s=open(f,encoding="utf-8").read(); open(f,"w",encoding="utf-8").write(re.sub("width=\"[^\"]*\" height=\"[^\"]*\" viewBox=\"[^\"]*\"", f"width=\"{w}\" height=\"{h}\" viewBox=\"{b}\"", s, count=1))' source/vector/logo.svg "420 210 120 120"`. The slide background comes along as the first `<path>`: delete it for a transparent logo. The official logo from step 3 beats a cut-out; chart numbers come from `deck.txt` and the reading set, not from SVG paths.

## Keynote

The exports: File → Export To (Keynote for iCloud: More → Download a Copy), presenter notes and skipped slides ticked in the PDF dialog. A current Keynote keeps charts as charts in the PPTX, so `deck.md` lists their numbers.

Without an export, unpack the file into its own folder (Keynote writes UTF-8 names without the zip flag; this keeps accented names readable):

```sh
<skill>/run python3 -I -c 'import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
for i in z.infolist():
    if not i.flag_bits & 0x800: i.filename = i.filename.encode("cp437").decode("utf-8", "replace")
    z.extract(i, sys.argv[2])' source/deck.key source/key
```

A `.key` that is a folder is already unpacked: copy the received folder straight to `source/key/` (`cp -R "source/<received name>" source/key`; for a revised deck, after everything has moved to `source/v1/`, above); it needs no plain name. Text sits in compressed `Index/*.iwa` files (in a package, folder or zipped: `Index.zip`) that common tools don't read: get it from an export or the user (Keynote '09 and older: plain XML in a top-level `*.apxl`).

Pictures and movies sit in `Data/` (top level in Keynote '09 and older): copy the originals to `source/media/key/`, leaving out thumbnails (`st-…`, `st<N>-…`, `mt-…`), movie stills (`posterImage-…`) and preview copies (256 px on the long side, usually `…-small-<n>`; go by size, as a name with a dot loses the `-small`). A `-small-` preview without its original is all the deck holds of that picture: ask for the original. Convert TIFF with `<skill>/run python3 -I <skill>/scripts/images.py photos source/media/key/<name>.tiff assets/photos` and a PDF picture (vector) with `mkdir -p assets/photos && <skill>/run pdftocairo -svg source/media/key/<name>.pdf assets/photos/<name>.svg`; for HEIC ask for JPG or PNG.

## Google Slides

File → Download → PowerPoint (.pptx) and PDF; the PPTX carries the speaker notes.

## Slide images

Copy them to `source/pages/` as `p-01.png`, `p-02.png`, … in slide order (ask when the names don't tell), OCR each (`<skill>/run tesseract source/pages/p-01.png source/ocr/p-01 -l <lang>`, `<lang>` as under PDF) and check it against the picture. Logos, photos and charts cropped from a screenshot are too small for a stage: ask for the originals; for HEIC, ask for JPG or PNG.

## Brand fonts

Brand font files (licence: stagecraft.md, Content) go to `assets/fonts/brand/`, best as `.woff2` (`.woff`, `.ttf`, `.otf` are larger), one rule per file in `assets/fonts/brand.css`:

```css
@font-face{font-family:"Acme Sans";src:url("brand/AcmeSans-Bold.woff2") format("woff2");font-weight:700;font-style:normal}
```

`format()` is `woff2`, `woff`, `truetype` or `opentype`; a variable font gets one rule with a range (`font-weight:100 900`). Link it in `show.html` beside the Google Fonts file (`<link rel="stylesheet" href="assets/fonts/brand.css">`), not inside `fonts.css`, which `<skill>/scripts/fonts.py` rewrites. The build inlines its `url()`s, relative to the CSS file.
