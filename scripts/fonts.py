#!/usr/bin/env python3
"""Download Google Fonts as local woff2 files so the show runs offline. Stdlib only.

usage: fonts.py OUT_DIR SPEC [SPEC ...] [--subsets latin,latin-ext]
  SPEC is a css2 family spec, e.g. "Inter:wght@400;700" or "Fraunces:ital,wght@0,400..900;1,400..900"
  (variable ranges like 400..900 give one file per subset). A static family takes listed weights
  only: "Poppins:wght@400;700", not "Poppins:wght@400..700".
Writes OUT_DIR/fonts.css with @font-face rules pointing at the local files;
link it as <link rel="stylesheet" href="assets/fonts/fonts.css"> and build.py inlines it.
An existing fonts.css is merged: a run replaces the rules of the families it downloads and keeps
every other rule (other families, hand-written local @font-face), so families can be added one
call at a time. To drop a family, delete its rules, or delete fonts.css and re-run with the rest.
A failed download saves nothing; re-run the same command.
"""
import argparse, os, re, sys, urllib.error, urllib.parse, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
FACE = re.compile(r"(?:/\*(?:(?!\*/).)*\*/\s*)?@font-face\s*\{[^}]*\}", re.S)  # one rule with its leading comment


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def family(rule):
    m = re.search(r"font-family:\s*(['\"]?)([^;'\"}]+?)\1\s*[;}]", rule)
    return m.group(2).strip() if m else None


def write_atomic(path, data):
    """Write a temp file next to path, then rename it: path never holds a partial or empty write."""
    tmp = path + ".part"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def merge(old_css, families, new_rules):
    """Old fonts.css minus the rules of `families` (casefolded), with new_rules where the first of them stood."""
    parts, pos, at = [], 0, None
    for m in FACE.finditer(old_css):
        parts.append(old_css[pos:m.start()].strip())
        if (family(m.group(0)) or "").casefold() in families:
            at = len(parts) if at is None else at
        else:
            parts.append(m.group(0))
        pos = m.end()
    parts.append(old_css[pos:].strip())
    at = len(parts) if at is None else at
    return [p for p in parts[:at] if p] + new_rules + [p for p in parts[at:] if p]


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("out")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--subsets", default="latin,latin-ext")
    a = ap.parse_args()
    out, specs, subsets = a.out, a.specs, set(a.subsets.split(","))
    os.makedirs(out, exist_ok=True)
    q = "&".join("family=" + urllib.parse.quote(s, safe=":;,@.") for s in specs) + "&display=swap"
    try:
        css = get("https://fonts.googleapis.com/css2?" + q).decode()
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
        sys.exit(f"Google Fonts refused {' '.join(specs)} (HTTP 400): check each family name, and give a static family "
                 f"listed weights (\"Poppins:wght@400;700\") instead of a range (400..700); fonts.css unchanged")
    blocks = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{.*?\})", css, re.S)
    if not blocks:
        sys.exit("no @font-face blocks returned; check the family spec")
    kept, files = [], 0
    for subset, block in blocks:
        if subset not in subsets:
            continue
        fam = re.search(r"font-family:\s*'([^']+)'", block).group(1)
        style = re.search(r"font-style:\s*(\w+)", block).group(1)
        weight = re.search(r"font-weight:\s*([\d ]+)", block).group(1).strip().replace(" ", "-")
        url = re.search(r"url\((https://[^)]+)\)", block).group(1)
        name = f"{re.sub(r'[^a-z0-9]+', '-', fam.lower())}-{weight}-{style}-{subset}.woff2"
        path = os.path.join(out, name)
        if not os.path.exists(path) or os.path.getsize(path) == 0:  # 0 bytes: a failed download
            data = get(url)
            if data[:4] != b"wOF2":
                sys.exit(f"{url} returned no woff2 file ({len(data)} bytes); {name} not saved")
            write_atomic(path, data)
            files += 1
        kept.append(f"/* {subset} */\n" + block.replace(url, name))
    if not kept:
        sys.exit(f"no @font-face rules for the subsets {','.join(sorted(subsets))}; fonts.css unchanged")
    css_path = os.path.join(out, "fonts.css")
    old = open(css_path, encoding="utf-8").read() if os.path.exists(css_path) else ""
    run = {(family(b) or "").casefold() for _, b in blocks}
    write_atomic(css_path, ("\n".join(merge(old, run, kept)) + "\n").encode("utf-8"))
    others = sorted({f for m in FACE.finditer(old) if (f := family(m.group(0))) and f.casefold() not in run}, key=str.casefold)
    total = sum(os.path.getsize(os.path.join(out, n)) for n in os.listdir(out) if n.endswith(".woff2"))
    print(f"{len(kept)} @font-face rules, {files} new files, {total:,} bytes of woff2 in {out}")
    if others:
        print(f"fonts.css also keeps the rules of {', '.join(others)} (not part of this run); delete them there if the show no longer uses them")


if __name__ == "__main__":
    main()
