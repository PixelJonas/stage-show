#!/usr/bin/env python3
"""Inventory a PPTX for re-staging. Stdlib only.

usage: extract_pptx.py DECK.pptx OUT_DIR [--max-media-mb N]
writes
  OUT_DIR/deck.md      every slide in order: title, text (with list levels), tables, SmartArt,
                       chart data, images (with alt text), video/audio, links, speaker notes;
                       then each distinct footer and each text on the masters and layouts the
                       slides use, once, with its slides. Anything it cannot read is marked
                       [warning] in place and listed at the end.
  OUT_DIR/media/       slide images, backgrounds, SVG icons, video/audio as sNN-<name>;
                       master/layout images (often logos) as master-<name>
  OUT_DIR/theme.json   slide size, colours and fonts of the theme most slides use, most used fonts and colours
--max-media-mb N: largest single file copied to media/ (default 256); all copies together stop at 8x that.
No rendering: for slide pictures ask for a PDF export too (SKILL.md step 2).
"""
import argparse, collections, json, os, posixpath, re, sys, urllib.parse, zipfile
import xml.etree.ElementTree as ET

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "cx": "http://schemas.microsoft.com/office/drawing/2014/chartex",
    "asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
}
R, A, P, C, CX = ("{%s}" % NS[k] for k in ("r", "a", "p", "c", "cx"))
STRICT = "{http://purl.oclc.org/ooxml/presentationml/main}"
MAX_XML = 64 << 20                     # one XML part read into memory
BOMB_MIN, BOMB_RATIO = 16 << 20, 100   # bigger than this and compressed more than 100:1 = zip bomb
AV = {A + "videoFile": "video", A + "quickTimeFile": "video", A + "audioFile": "audio", A + "wavAudioFile": "audio"}
ODD_IMG = (".emf", ".wmf", ".tif", ".tiff", ".wdp", ".jxr")
ODD_AV = (".wmv", ".avi", ".asf", ".wma", ".mpg", ".mpeg")
QUIET = {"nvGrpSpPr", "grpSpPr", "extLst", "cxnSp"}   # structure and connector lines: nothing to inventory


class Skip(Exception):
    """One item that cannot be read; its message goes into deck.md as a warning."""


def mb(n):
    return f"{n / (1 << 20):.0f} MB"


def para_text(p):
    s = []
    for el in p.iter():
        if el.tag == A + "t":
            s.append(el.text or "")
        elif el.tag == A + "br":
            s.append("\n")
    return "".join(s).strip()


def sp_text(sp):
    return " / ".join(t for t in (para_text(p).replace("\n", " / ") for p in sp.findall(".//a:p", NS)) if t)


def slide_list(nums):
    runs, out = [], []
    for n in sorted(set(nums)):
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    for a, b in runs:
        out.append(str(a) if a == b else f"{a}-{b}")
    return ("slide " if len(set(nums)) == 1 else "slides ") + ", ".join(out)


def label(el):
    c = next(el.iter(P + "cNvPr"), None)
    return (c.get("descr") or c.get("name") or "") if c is not None else ""


class Pkg:
    def __init__(self, path, out, media_cap):
        try:
            self.z = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError) as e:
            sys.exit(f"{path}: not a PPTX ({e}). A legacy .ppt or a password-protected deck must be re-saved "
                     "as an unprotected .pptx; for Keynote see SKILL.md step 2.")
        self.infos = {i.filename: i for i in self.z.infolist()}
        self.lower = {n.lower(): n for n in self.infos}
        self.media = os.path.join(out, "media")
        self.media_cap, self.total_cap = media_cap, 8 * media_cap
        self.written, self.copied, self.names, self.sizes, self.warnings = 0, {}, set(), {}, []

    def find(self, part):
        for cand in (part, urllib.parse.unquote(part)):
            if cand in self.infos:
                return cand
            if cand.lower() in self.lower:   # part names are case-insensitive
                return self.lower[cand.lower()]
        return None

    def info(self, part, cap):
        name = self.find(part)
        if name is None:
            raise Skip(f"{part} is referenced but not in the file")
        i = self.infos[name]
        if i.file_size > BOMB_MIN and i.file_size > BOMB_RATIO * max(i.compress_size, 1):
            raise Skip(f"{name} would expand {i.file_size // max(i.compress_size, 1)}:1 to {mb(i.file_size)}; refused")
        if i.file_size > cap:
            raise Skip(f"{name} is {mb(i.file_size)}, over the {mb(cap)} limit (raise it with --max-media-mb)")
        return i

    def xml(self, part):
        data = self.z.read(self.info(part, MAX_XML))
        if data[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\0" in data:   # UTF-16/32 would hide a DTD from the check below
            raise Skip(f"{part} is not UTF-8; refused")
        if b"<!DOCTYPE" in data:   # OOXML parts never carry a DTD
            raise Skip(f"{part} contains a DTD; refused")
        try:
            return ET.fromstring(data)
        except (ET.ParseError, ValueError, LookupError) as e:   # the last two: a declared encoding expat cannot read
            raise Skip(f"{part} is not well-formed XML ({e})") from None

    def rels(self, part):
        d, b = posixpath.split(part)
        rp = posixpath.join(d, "_rels", b + ".rels")
        out = {}
        if self.find(rp) is None:
            return out
        for r in self.xml(rp).findall("rel:Relationship", NS):
            tgt, ext = r.get("Target") or "", r.get("TargetMode") == "External"
            if not ext:   # "/ppt/media/x.png" is package-absolute, anything else relative to the part
                tgt = posixpath.normpath(tgt[1:] if tgt.startswith("/") else posixpath.join(d, tgt))
            out[r.get("Id")] = ((r.get("Type") or "").rsplit("/", 1)[-1], tgt, ext)
        return out

    def copy(self, part, prefix):
        """Stream one member into media/ under the size limits; returns the file name."""
        key = self.find(part) or part
        if key in self.copied:
            return self.copied[key]
        i = self.info(part, self.media_cap)
        if self.written + i.file_size > self.total_cap:
            raise Skip(f"{i.filename} skipped: media/ would pass {mb(self.total_cap)} in total (raise with --max-media-mb)")
        stem, ext = posixpath.splitext(posixpath.basename(i.filename))
        stem, ext = re.sub(r"[^\w.-]+", "_", stem)[:80] or "file", re.sub(r"[^\w.]", "", ext)[:10]
        name, k = f"{prefix}-{stem}{ext}", 1
        while name in self.names:
            k += 1
            name = f"{prefix}-{stem}-{k}{ext}"
        dst, n = os.path.join(self.media, name), 0
        try:
            with self.z.open(i) as src, open(dst + ".part", "wb") as f:
                while chunk := src.read(1 << 20):
                    n += len(chunk)
                    if n > i.file_size:
                        raise Skip(f"{i.filename} is bigger than its zip entry claims; refused")
                    f.write(chunk)
            os.replace(dst + ".part", dst)
        except BaseException:
            if os.path.exists(dst + ".part"):
                os.remove(dst + ".part")
            raise
        self.written += n
        self.sizes[name] = n
        self.names.add(name)
        self.copied[key] = name
        return name

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")
        return f"  [warning] {msg}"


def picture(pkg, blip, alt, rl, prefix, what="image"):
    """Items for one a:blip: the SVG original when there is one, its PNG fallback, or a linked file."""
    names = []
    svg = blip.find("a:extLst/a:ext/asvg:svgBlip", NS)
    if svg is not None:
        try:
            names.append(pkg.copy(rl[svg.get(R + "embed")][1], prefix))
        except (Skip, KeyError) as e:
            yield ("warn", f"SVG version of {what} '{alt}' missing ({e})")
    rid, lid = blip.get(R + "embed"), blip.get(R + "link")
    if rid:
        if rid not in rl:
            raise Skip(f"{what} '{alt}' points at relationship {rid}, which does not exist")
        try:
            names.append(pkg.copy(rl[rid][1], prefix))
        except Skip as e:
            raise Skip(f"{what} '{alt}': {e}") from None
    elif lid in rl:
        yield ("linked", what, rl[lid][1], alt)
    if names:
        yield ("img", what, names, alt)


def av_items(pkg, el, nv, rl, prefix):
    """Video/audio on a p:pic: the embedded file (p14:media or a:*File), or the link for online media."""
    kind = next((AV[e.tag] for e in nv if e.tag in AV), "media")
    rids = [m.get(R + "embed") for m in nv.iterfind("p:extLst/p:ext/p14:media", NS)]
    rids += [e.get(R + "link") or e.get(R + "embed") for e in nv if e.tag in AV]
    files, links = [], []
    for rid in dict.fromkeys(r for r in rids if r):
        if rid not in rl:
            yield ("warn", f"{kind} '{label(el)}' points at relationship {rid}, which does not exist")
        elif rl[rid][2]:
            links.append(rl[rid][1])
        else:
            files.append(pkg.copy(rl[rid][1], prefix))
    poster = []
    blip = el.find("p:blipFill/a:blip", NS)
    if blip is not None and blip.get(R + "embed") in rl:
        poster = [pkg.copy(rl[blip.get(R + "embed")][1], prefix)]
    yield ("av", kind, list(dict.fromkeys(files)), links, poster, label(el))


def pts(el, ns, text_of):
    """{idx: value} of a chart data reference; points can be sparse, so map by idx."""
    if el is None:
        return {}
    lvl = el.find(f".//{ns}lvl")   # multi-level categories: first level only
    src = lvl if lvl is not None else el
    return {int(p.get("idx", i)): text_of(p) for i, p in enumerate(src.iter(f"{ns}pt"))}


def title_of(t):
    return " ".join(e.text or "" for e in t.iter() if e.tag in (A + "t", C + "v", CX + "v")).strip() if t is not None else ""


def chart(pkg, part):
    x = pkg.xml(part)
    pa = x.find("c:chart/c:plotArea", NS)
    kinds = [e.tag.split("}")[1][:-5] for e in (pa if pa is not None else []) if e.tag.endswith("Chart")]
    title = title_of(x.find("c:chart/c:title", NS))
    out, v, found = ([f"title: {title}"] if title else []), lambda p: p.findtext(C + "v") or "", 0
    for ser in x.iter(C + "ser"):
        name = " ".join(t.text or "" for t in ser.findall("c:tx//c:v", NS)) or "?"
        xv, yv = ser.find("c:xVal", NS), ser.find("c:yVal", NS)
        cat = pts(ser.find("c:cat", NS) if xv is None else xv, C, v)
        val = pts(ser.find("c:val", NS) if yv is None else yv, C, v)
        size = pts(ser.find("c:bubbleSize", NS), C, v)
        idx, found = sorted(set(cat) | set(val)), found + any(val.values())
        if xv is not None:   # scatter/bubble: points, not categories
            vals = ", ".join("(" + ", ".join(s for s in (cat.get(i, "?"), val.get(i, "?"), size.get(i)) if s is not None) + ")" for i in idx)
        else:
            vals = ", ".join(f"{cat.get(i, i + 1)}={val.get(i, '')}" for i in idx)
        out.append(f"series {name}: {vals}")
    if not found:
        raise Skip(f"chart {part} ({'/'.join(kinds) or '?'}) has no cached values: ask for the numbers")
    return "/".join(kinds) or "chart", out


def chartex(pkg, part):
    """Office 2016 chart types (waterfall, funnel, treemap, sunburst, histogram, box & whisker, map)."""
    x = pkg.xml(part)
    data = {d.get("id"): d for d in x.iterfind("cx:chartData/cx:data", NS)}
    title = title_of(x.find("cx:chart/cx:title", NS))
    kinds, out, found = [], ([f"title: {title}"] if title else []), 0
    for s in x.iter(CX + "series"):
        kinds.append(s.get("layoutId", "?"))
        name = " ".join(t.text or "" for t in s.findall("cx:tx//cx:v", NS)) or "?"
        di = s.find("cx:dataId", NS)
        d = data.get(di.get("val") if di is not None else "0")
        if d is None:
            continue
        num = d.find("cx:numDim[@type='val']", NS)
        num = num if num is not None else d.find("cx:numDim[@type='size']", NS)
        cat = pts(d.find("cx:strDim[@type='cat']", NS), CX, lambda p: p.text or "")
        val = pts(num, CX, lambda p: p.text or "")
        found += any(val.values())
        out.append(f"series {name}: " + ", ".join(f"{cat.get(i, i + 1)}={val.get(i, '')}" for i in sorted(set(cat) | set(val))))
    kind = "/".join(dict.fromkeys(kinds)) or "?"
    if not found:
        raise Skip(f"chart {part} ({kind}, an Office 2016 chart type) has no readable data: ask for the numbers")
    return kind, out


def smartart(pkg, part, prefix):
    """SmartArt text from the diagram data part, nested by its parent/child connections."""
    x = pkg.xml(part)
    text = lambda pt: " / ".join(t for t in (para_text(p) for p in pt.iterfind("dgm:t/a:p", NS)) if t)
    pts_ = {pt.get("modelId"): pt for pt in x.iterfind("dgm:ptLst/dgm:pt", NS)}
    kids = collections.defaultdict(list)
    for c in x.iterfind("dgm:cxnLst/dgm:cxn", NS):
        if c.get("type", "parOf") == "parOf":
            kids[c.get("srcId")].append((int(c.get("srcOrd", 0)), c.get("destId")))
    lines, seen = [], set()

    def walk(mid, lvl):
        for _, d in sorted(kids.get(mid, [])):
            if d in seen or d not in pts_:
                continue
            seen.add(d)
            if pts_[d].get("type", "node") in ("node", "asst"):
                if text(pts_[d]):
                    lines.append((lvl, text(pts_[d])))
                walk(d, lvl + 1)
    for mid, pt in pts_.items():
        if pt.get("type") == "doc":
            seen.add(mid)
            walk(mid, 0)
    if not lines:   # no connections: document order
        lines = [(0, text(pt)) for pt in pts_.values() if pt.get("type", "node") in ("node", "asst") and text(pt)]
    imgs, drl = [], pkg.rels(part)
    for b in x.iter(A + "blip"):
        if b.get(R + "embed") in drl:
            imgs.append(pkg.copy(drl[b.get(R + "embed")][1], prefix))
    return lines, imgs


def shapes(pkg, node, rl, links, prefix):
    """Items for every shape under node in reading order; a shape that fails becomes a warning."""
    for el in node if node is not None else []:
        tag = el.tag.split("}")[-1]
        if tag in QUIET:
            continue
        try:
            items = list(shape(pkg, el, tag, rl, links, prefix))
        except Skip as e:
            items = [("warn", str(e))]
        except Exception as e:
            items = [("warn", f"<{tag}> '{label(el)}' could not be read ({type(e).__name__}: {e})")]
        yield from items


def shape(pkg, el, tag, rl, links, prefix):
    if tag == "grpSp":
        yield from shapes(pkg, el, rl, links, prefix)
    elif tag == "AlternateContent":
        # exactly one branch: the first Choice with readable content, else the Fallback
        first = None
        for branch in el.findall("mc:Choice", NS) + el.findall("mc:Fallback", NS):
            bl = set()
            items = list(shapes(pkg, branch, rl, bl, prefix))
            first = first or (items, bl)
            if any(i[0] != "warn" for i in items):
                links |= bl
                yield from items
                return
        if first:
            links |= first[1]
            yield from first[0]
    elif tag == "sp":
        ph = el.find("p:nvSpPr/p:nvPr/p:ph", NS)
        kind = ph.get("type", "body") if ph is not None else "text"
        if kind in ("sldNum", "dt"):
            return
        if kind == "ftr":
            t = sp_text(el)
            if t:
                yield ("footer", t)
            return
        for p in el.findall(".//a:p", NS):
            t = para_text(p)
            if t:
                ppr = p.find("a:pPr", NS)
                lvl = int(ppr.get("lvl", 0)) if ppr is not None else 0
                yield ("title" if kind in ("title", "ctrTitle") else "p", t, lvl)
        blip = el.find("p:spPr/a:blipFill/a:blip", NS)
        if blip is not None:
            yield from picture(pkg, blip, label(el), rl, prefix, "shape filled with an image")
    elif tag == "pic":
        nv = el.find("p:nvPicPr/p:nvPr", NS)
        if nv is not None and (any(e.tag in AV for e in nv) or nv.find("p:extLst/p:ext/p14:media", NS) is not None):
            yield from av_items(pkg, el, nv, rl, prefix)
        else:
            blip = el.find("p:blipFill/a:blip", NS)
            if blip is None:
                raise Skip(f"picture '{label(el)}' has no image")
            yield from picture(pkg, blip, label(el), rl, prefix)
    elif tag == "graphicFrame":
        gd = el.find("a:graphic/a:graphicData", NS)
        uri = gd.get("uri", "") if gd is not None else ""
        tbl, ch, cxc, dg = (el.find(f".//{q}", NS) for q in ("a:tbl", "c:chart", "cx:chart", "dgm:relIds"))
        if tbl is not None:
            for tr in tbl.findall("a:tr", NS):
                yield ("row", " | ".join(" ".join(para_text(p) for p in tc.findall(".//a:p", NS)).strip() for tc in tr.findall("a:tc", NS)))
        elif ch is not None or cxc is not None:
            ref = ch if ch is not None else cxc
            if ref.get(R + "id") not in rl:
                raise Skip(f"chart '{label(el)}' points at relationship {ref.get(R + 'id')}, which does not exist")
            yield ("chart", *(chart if ch is not None else chartex)(pkg, rl[ref.get(R + "id")][1]))
        elif dg is not None:
            if dg.get(R + "dm") not in rl:
                raise Skip(f"SmartArt '{label(el)}' has no data part")
            yield ("smartart", *smartart(pkg, rl[dg.get(R + "dm")][1], prefix))
        else:
            blip = el.find(".//a:blip", NS)   # embedded objects (OLE) carry a preview picture
            if blip is None:
                raise Skip(f"unsupported object '{label(el)}' ({uri or 'no type'}): check the slide picture")
            yield from picture(pkg, blip, label(el), rl, prefix, f"preview of embedded object ({uri.rsplit('/', 1)[-1]})")
    else:
        what = "ink or content part" if tag == "contentPart" else f"unsupported element <{tag}>"
        raise Skip(f"{what} '{label(el)}': check the slide picture")
    if tag in ("sp", "pic"):
        for h in el.iter(A + "hlinkClick"):
            rid = h.get(R + "id")
            if rid in rl and rl[rid][2]:
                links.add(rl[rid][1])


def render(pkg, md, item, where):
    k = item[0]
    if k == "title":
        md.append(f"**{item[1]}**")
    elif k == "p":
        md.append("  " * item[2] + "- " + item[1].replace("\n", " / "))
    elif k == "row":
        md.append("  | " + item[1])
    elif k == "img":
        _, what, names, alt = item
        fb = f" (PNG fallback media/{names[1]})" if len(names) > 1 else ""
        md.append(f"  [{what} media/{names[0]}{fb}]" + (f" alt: {alt}" if alt else ""))
    elif k == "linked":
        md.append(pkg.warn(where, f"linked {item[1]} not in the file: {item[2]}" + (f" (alt: {item[3]})" if item[3] else "")))
    elif k == "av":
        _, kind, files, links, poster, name = item
        refs = [f"media/{f}" for f in files] + links
        md.append(f"  [{kind} {', '.join(refs) or '?'}]" + (f" poster media/{poster[0]}" if poster else "") + (f" name: {name}" if name else ""))
    elif k == "chart":
        md.append(f"  [chart {item[1]}] " + "; ".join(item[2]))
    elif k == "smartart":
        md.append("  [SmartArt]")
        md.extend("    " + "  " * lvl + "- " + t for lvl, t in item[1])
        md.extend(f"    [image media/{n}]" for n in item[2])
    elif k == "warn":
        md.append(pkg.warn(where, item[1]))


def theme_part(pkg, pres, prel, slide_parts):
    """The theme of the master most slides use (slide -> layout -> master -> theme), not a file-name sort."""
    used = collections.Counter()
    for sp in slide_parts:
        for kind, tgt, _ in pkg.rels(sp).values():
            if kind == "slideLayout":
                used.update(t for k, t, _ in pkg.rels(tgt).values() if k == "slideMaster")
    masters = [m for m, _ in used.most_common()]
    masters += [prel[i.get(R + "id")][1] for i in pres.iterfind("p:sldMasterIdLst/p:sldMasterId", NS) if i.get(R + "id") in prel]
    for m in masters:
        for kind, tgt, _ in pkg.rels(m).values():
            if kind == "theme" and pkg.find(tgt):
                return pkg.find(tgt), m, used
    return None, None, used


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("deck")
    ap.add_argument("out")
    ap.add_argument("--max-media-mb", type=int, default=256)
    a = ap.parse_args()
    pkg = Pkg(a.deck, a.out, a.max_media_mb << 20)
    os.makedirs(pkg.media, exist_ok=True)
    try:
        main_part = next((t for k, t, e in pkg.rels("").values() if k == "officeDocument"), "ppt/presentation.xml")
        pres, prel = pkg.xml(main_part), pkg.rels(main_part)
    except Skip as e:   # without the presentation part and its relationships there are no slides to list
        sys.exit(f"{a.deck}: {e}")
    if pres.tag.startswith(STRICT):
        sys.exit(f"{a.deck}: Strict Open XML is not supported; ask for a standard .pptx (or a PDF)")
    sz = pres.find("p:sldSz", NS)
    theme = {"slide_size_emu": [int(sz.get("cx")), int(sz.get("cy"))] if sz is not None else None}
    if sz is not None:
        theme["aspect"] = round(int(sz.get("cx")) / int(sz.get("cy")), 3)
    md = [f"# {os.path.basename(a.deck)}", ""]
    fonts, colors, heads, slide_parts = collections.Counter(), collections.Counter(), [], []
    footers, uses = {}, collections.defaultdict(set)   # footer text -> slides; master/layout part -> slides

    n = 0
    for n, sid in enumerate(pres.findall("p:sldIdLst/p:sldId", NS), 1):
        where, pre = f"slide {n}", f"s{n:02d}"
        md.append(f"## Slide {n}")
        try:
            rid = sid.get(R + "id")
            if rid not in prel:
                raise Skip(f"slide {n} points at relationship {rid}, which does not exist")
            part = prel[rid][1]
            sx, rl = pkg.xml(part), pkg.rels(part)
        except Skip as e:
            md += [pkg.warn(where, f"slide skipped: {e}"), ""]
            heads.append((len(md) - 3, False))
            continue
        hidden = sx.get("show") == "0"
        heads.append((len(md) - 1, hidden))
        slide_parts.append(part)
        try:
            for kind, tgt, _ in rl.values():
                if kind == "slideLayout":
                    uses[tgt].add(n)
                    for k2, t2, _ in pkg.rels(tgt).values():
                        if k2 == "slideMaster":
                            uses[t2].add(n)
        except Skip:
            pass
        links, items = set(), []
        bg = sx.find("p:cSld/p:bg/p:bgPr/a:blipFill/a:blip", NS)
        if bg is not None:
            try:
                items += list(picture(pkg, bg, "", rl, pre, "background image"))
            except Skip as e:
                items.append(("warn", str(e)))
        items += list(shapes(pkg, sx.find("p:cSld/p:spTree", NS), rl, links, pre))
        for item in items:
            if item[0] == "footer":
                footers.setdefault(item[1], []).append(n)
            else:
                render(pkg, md, item, where)
        for e in sx.iter(A + "latin"):
            if e.get("typeface"):
                fonts[e.get("typeface")] += 1
        for e in sx.iter(A + "srgbClr"):
            colors["#" + (e.get("val") or "").upper()] += 1
        for url in sorted(links):
            md.append(f"  [link] {url}")
        for kind, tgt, ext in rl.values():
            if kind != "notesSlide":
                continue
            try:
                for sp in pkg.xml(tgt).iter(P + "sp"):
                    ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
                    if ph is not None and ph.get("type") == "body":
                        txt = "\n".join(t for t in (para_text(p) for p in sp.findall(".//a:p", NS)) if t)
                        if txt:
                            md.append("  Notes: " + txt.replace("\n", "\n  "))
            except Skip as e:
                md.append(pkg.warn(where, f"speaker notes not read: {e}"))
        md.append("")
    if any(h for _, h in heads):   # a PDF export leaves hidden slides out, so its page numbers shift
        page = 0
        for i, hidden in heads:
            if hidden:
                md[i] += " (hidden: not in a PDF export)"
            else:
                page += 1
                md[i] += f" (PDF page {page})"

    shared = {}   # text on a master or layout (no placeholder prompts) -> slides that use it
    for part in sorted(p for p in pkg.infos if re.match(r"ppt/(slideMasters|slideLayouts)/[^/]+\.xml$", p)):
        if uses.get(part):
            try:
                for sp in pkg.xml(part).iter(P + "sp"):
                    ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
                    t = sp_text(sp) if ph is None or ph.get("type") == "ftr" else ""
                    if t and t not in footers:
                        shared.setdefault(t, set()).update(uses[part])
            except Skip as e:
                pkg.warn(posixpath.basename(part), str(e))
        try:
            for kind, tgt, ext in pkg.rels(part).values():
                if kind == "image" and not ext:
                    try:
                        pkg.copy(tgt, "master")
                    except Skip as e:
                        pkg.warn(posixpath.basename(part), str(e))
        except Skip as e:
            pkg.warn(posixpath.basename(part), str(e))
    try:
        th, master, used = theme_part(pkg, pres, prel, slide_parts)
        if th is None:
            th = next(iter(sorted(p for p in pkg.infos if re.match(r"ppt/theme/theme\d+\.xml$", p))), None)
            if th:
                pkg.warn("theme", f"no master links a theme; theme.json uses {th}")
        if th:
            theme["theme_part"] = th
            if len(used) > 1:
                theme["masters_used"] = {posixpath.basename(m): c for m, c in used.most_common()}
                pkg.warn("theme", f"{len(used)} slide masters in use; theme.json follows {posixpath.basename(master)}")
            tx = pkg.xml(th)
            cs = tx.find(".//a:clrScheme", NS)
            if cs is not None:
                theme["colors"] = {}
                for c in cs:
                    v = c.find("a:srgbClr", NS)
                    s = c.find("a:sysClr", NS)
                    v = v.get("val") if v is not None else (s.get("lastClr") if s is not None else None)
                    theme["colors"][c.tag.split("}")[1]] = "#" + v.upper() if v else None
            for which in ("majorFont", "minorFont"):
                f = tx.find(f".//a:fontScheme/a:{which}/a:latin", NS)
                if f is not None:
                    theme[which] = f.get("typeface")
    except Skip as e:
        pkg.warn("theme", str(e))
    if footers or shared:
        md += ["## Footers, masters and layouts (where it shows: the page pictures)", ""]
        md += [f"- [footer] {t} ({slide_list(ns)})" for t, ns in sorted(footers.items(), key=lambda x: (min(x[1]), x[0]))]
        md += [f"- [master] {t} ({slide_list(ns)})" for t, ns in sorted(shared.items(), key=lambda x: (min(x[1]), x[0]))]
        md.append("")
    theme["fonts_used"] = fonts.most_common(8)
    theme["colors_used"] = colors.most_common(12)
    odd = sorted(f for f in pkg.copied.values() if f.lower().endswith(ODD_IMG))
    if odd:
        md.append("Images in formats a browser cannot show (ask for PNG/SVG or the source files): " + ", ".join(odd))
    odd = sorted(f for f in pkg.copied.values() if f.lower().endswith(ODD_AV))
    if odd:
        md.append("Video/audio Chrome will not play (ask for MP4 or WebM): " + ", ".join(odd))
    big = sorted(f for f, sz in pkg.sizes.items() if sz > 25 << 20)
    if big:
        md.append("Large files (base64 inlining adds a third; trim, re-encode or leave them out): "
                  + ", ".join(f"{f} ({mb(pkg.sizes[f])})" for f in big))
    if pkg.warnings:
        md += ["", "## Warnings (content that may be missing above: check the slide pictures)", ""]
        md += [f"- {w}" for w in pkg.warnings]
    with open(os.path.join(a.out, "deck.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(a.out, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=1, ensure_ascii=False)
    print(f"{n} slides -> {os.path.join(a.out, 'deck.md')}, {len(pkg.copied)} files -> {os.path.join(a.out, 'media')}, theme -> {os.path.join(a.out, 'theme.json')}"
          + (f"\n{len(pkg.warnings)} WARNINGS: read the end of deck.md" if pkg.warnings else ""))


if __name__ == "__main__":
    main()
