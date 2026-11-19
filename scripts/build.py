#!/usr/bin/env python3
"""Single-file builds for a stage show. Stdlib only.

  build.py build SRC.html OUT.html [--allow-external]
      Inline every local asset into one offline HTML file:
      <link rel=stylesheet href="assets/..."> -> <style> (its url()s inlined too),
      <script src="assets/..."> -> inline <script> (a deferred one moves to the end
      of <body>, so it still runs after the page is parsed), and every literal path
      into assets/ -> data: URI. A literal path is one complete path in quotes,
      backticks without ${...}, url(...), an unquoted attribute or a srcset entry;
      a leading ./ is fine, ?query is dropped, #fragment is kept.
      HTML comments stay as they are and are not searched.
      Fails on missing files, on paths leading out of assets/, on every assets/
      path still in the output (paths that code assembles, like 'assets/logos/' +
      name, can't be inlined) and on external resources (CDN scripts, web fonts,
      remote images); plain <a href> links are fine.
  build.py strip IN.html OUT.html
      Reading copy: data: URIs and long SVG paths shortened, so an agent can
      read a built file.
  build.py unbundle IN.html DIR
      Reverse of build for a file you only have built: writes DIR/show.html
      plus DIR/assets/inline/<hash>.<ext>, then checks that `build` turns it back
      into the same bytes and says so. Data URIs that build would write
      differently (parameters such as ;charset=, unknown types) stay inline.
"""
import base64, bisect, gzip, hashlib, mimetypes, os, re, sys, urllib.parse

MIME = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
        ".svg": "image/svg+xml", ".webp": "image/webp", ".avif": "image/avif", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".ico": "image/x-icon", ".css": "text/css",
        ".js": "text/javascript", ".json": "application/json", ".mp4": "video/mp4", ".webm": "video/webm",
        ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav"}
EXT = {v: k for k, v in MIME.items()} | {"image/jpeg": ".jpg", "image/svg+xml": ".svg"}
TEXT = (".json", ".svg", ".css", ".js", ".mjs", ".html", ".htm", ".txt", ".csv", ".vtt")  # scanned for assets/ paths when inlined as data:
DATA_URI = re.compile(r"data:([a-z0-9.+/-]+)(;[a-z0-9=.+-]+)*;base64,([A-Za-z0-9+/=]+)", re.I)
EXTERNAL = [
    (re.compile(r"<(?:script|img|source|video|audio|iframe|embed)\b[^>]*\bsrc\s*=\s*[\"']?(?:https?:)?//", re.I), "remote src"),
    (re.compile(r"<link\b(?=[^>]*\brel\s*=\s*[\"']?(?:stylesheet|preload|modulepreload|icon))[^>]*\bhref\s*=\s*[\"']?(?:https?:)?//", re.I), "remote <link>"),
    (re.compile(r"url\(\s*[\"']?(?:https?:)?//", re.I), "remote url()"),
    (re.compile(r"@import\s+(?:url\()?\s*[\"']?(?:https?:)?//", re.I), "remote @import"),
]

# One HTML token: a comment, a raw-text element (its content is never markup, so a "<!--" inside a
# script string is just text), or any other start tag (quoted attribute values may hold "<!--" or ">").
TAG_REST = r"""[^>"']*(?:(?:"[^"]*"|'[^']*')[^>"']*)*"""
TOKEN = re.compile(r"<!--(?:>|->|[\s\S]*?(?:--!?>|\Z))"
                   r"|<(script|style|textarea|title)\b(" + TAG_REST + r")>([\s\S]*?)(</\1(?=[\s/>])[^>]*>|\Z)"
                   r"|<[A-Za-z]" + TAG_REST + ">", re.I)
ATTR = re.compile(r"""([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")

# A literal path the build inlines: assets/<file>, optional ./ in front, ?query (dropped), #fragment (kept).
PATH = r"(?:\./)?assets/[^\s\"'`()<>?#$\\]+"
PATH_Q = r"(?:\./)?assets/(?:[^\n\r\"'`<>?#$\\]|\$(?!\{))+"                   # in quotes: spaces and () allowed
TAIL = r"(\?[^\s\"'`()<>#]*)?(#[^\s\"'`()<>]*)?"
QUOTED = re.compile(r"([\"'`])(" + PATH_Q + ")" + TAIL + r"\1")
URL_FN = re.compile(r"(\(\s*)(" + PATH + ")" + TAIL + r"(?=\s*\))")
UNQUOTED = re.compile(r"(=\s*)(" + PATH + ")" + TAIL + r"(?=[\s>]|$)")            # start tags only
SRCSET = re.compile(r"(\b(?:image)?srcset\s*=\s*)(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
SRCSET_URL = re.compile(r"(?<![^\s,\"'])((?:\./)?assets/[^\s\"'`()<>?#$\\]+?)(\?[^\s,\"']*)?(#[^\s,\"']*)?(?=,*(?:[\s\"']|$))")
# Safety net: any assets/ path left after inlining (absolute http(s) URLs that merely contain /assets/ excepted).
NET = re.compile(r"(?<![\w-])assets\\?/|([\"'`])assets\1")
TOKEN_AT = re.compile(r"assets\\?/(?:[^\s\"'`()<>,;?#$]|\$(?!\{))*")
DROP_ON_INLINE = {"src", "defer", "async", "integrity", "crossorigin", "referrerpolicy", "fetchpriority", "charset", "blocking"}


def mime(path):
    ext = os.path.splitext(path)[1].lower()
    return MIME.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def data_uri(path):
    with open(path, "rb") as f:
        return f"data:{mime(path)};base64," + base64.b64encode(f.read()).decode()


def attrs(text):
    """Attributes of a tag (name lower-cased -> value, None for a bare attribute) and their raw text."""
    found = {}
    for m in ATTR.finditer(text):
        v = next((g for g in m.groups()[1:] if g is not None), None)
        found.setdefault(m.group(1).lower(), (v, m.group(0)))
    return {k: v for k, (v, _) in found.items()}, {k: raw for k, (_, raw) in found.items()}


def mask(text):
    """Base64 payloads of data: URIs replaced by same-length filler, so scans neither match inside them nor shift."""
    return DATA_URI.sub(lambda m: m.group(0)[:m.start(3) - m.start()] + "x" * len(m.group(3)), text)


def scan(text, origin, line, out):
    """Append (origin, line, snippet, reason) for every assets/ path left in text."""
    t = mask(text)
    for m in NET.finditer(t):
        i = m.start()
        lead = re.search(r"[^\s\"'`()<>=,]*$", t[max(0, i - 200):i]).group(0)
        if re.match(r"(?:https?:)?//", lead):
            continue                                          # part of a remote URL: EXTERNAL's business
        tok = m.group(0) if m.group(1) else TOKEN_AT.match(t, i).group(0)
        after, before = t[i + len(tok):i + len(tok) + 4], t[max(0, i - 4):i]
        runtime = (m.group(1) or (tok.endswith("/") and t[i - 1:i] in ("\"", "'", "`"))
                   or after.lstrip("\"'`").lstrip().startswith(("+", "${"))
                   or before.rstrip().rstrip("\"'`").rstrip().endswith(("+", "}")))
        snippet = t[max(0, i - 30):i + len(tok) + 30].replace("\n", " ")
        out.append((origin, line + t.count("\n", 0, i), tok, snippet, "assembled at runtime" if runtime else "not a literal path the build inlines"))


class Build:
    def __init__(self, src):
        self.src = src
        self.base = os.path.dirname(os.path.abspath(src))
        self.assets = os.path.join(self.base, "assets") + os.sep
        self.html = open(src, encoding="utf-8").read()
        self.nl = [m.start() for m in re.finditer("\n", self.html)]
        self.used, self.missing, self.outside, self.left = {}, {}, {}, []
        self.pieces = []  # (text, origin, first line, kind): kind "comment" is never scanned, "text" may hold </body>

    def line(self, i):
        return bisect.bisect_left(self.nl, i) + 1

    def resolve(self, rel, where):
        """Data URI for a literal assets/ path, or None (recorded as missing or outside)."""
        rel = rel[2:] if rel.startswith("./") else rel
        if rel.endswith("/"):
            return None                                       # a folder: code appends the name at runtime; scan() reports it
        p = os.path.normpath(os.path.join(self.base, rel))
        if not p.startswith(self.assets):
            self.outside.setdefault(rel, where)
            return None
        if not os.path.isfile(p) and "%" in rel:
            p = os.path.normpath(os.path.join(self.base, urllib.parse.unquote(rel)))   # Beta%20Corp.webp
        if not os.path.isfile(p) or not p.startswith(self.assets):
            self.missing.setdefault(rel, where)
            return None
        self.used[p] = os.path.getsize(p)
        if os.path.splitext(p)[1].lower() in TEXT:
            n = len(self.left)
            scan(open(p, encoding="utf-8", errors="replace").read(), os.path.relpath(p, self.base), 1, self.left)
            for k in range(n, len(self.left)):
                o, ln, tok, snip, _ = self.left[k]
                self.left[k] = (o, ln, tok, snip, "inside a file that is inlined as data:, where paths are not inlined; "
                                f"put this data into show.html instead (used at {where})")
        return data_uri(p)

    def literals(self, text, origin, line, tag=False):
        """Inline every literal assets/ path in text (a start tag, a script or a style body)."""
        def sub(rx, text, wrap):
            def rep(m):
                path, query, frag = m.group(2), m.group(3) or "", m.group(4) or ""
                uri = self.resolve(path, f"{origin}:{line + text.count(chr(10), 0, m.start())}")
                return wrap(m, path + query + frag if uri is None else uri + frag)
            return rx.sub(rep, text)

        def srcset(m):
            where = f"{origin}:{line + text.count(chr(10), 0, m.start())}"
            def rep(u):
                uri = self.resolve(u.group(1), where)
                return u.group(0) if uri is None else uri + (u.group(3) or "")
            return m.group(1) + SRCSET_URL.sub(rep, m.group(2))
        text = SRCSET.sub(srcset, text)
        text = sub(QUOTED, text, lambda m, v: m.group(1) + v + m.group(1))
        text = sub(URL_FN, text, lambda m, v: m.group(1) + v)
        if tag:
            text = sub(UNQUOTED, text, lambda m, v: m.group(1) + v)
        return text

    def asset_attr(self, value):
        """(path, query) when an attribute value is one literal assets/ path."""
        m = value is not None and re.fullmatch("(" + PATH_Q + ")" + TAIL, value)
        return (m.group(1), m.group(2) or "") if m else None

    def link(self, tag, i):
        a, _ = attrs(tag[5:-1])
        ref = self.asset_attr(a.get("href"))
        if not ref or "stylesheet" not in (a.get("rel") or "").lower().split():
            return False
        rel = ref[0][2:] if ref[0].startswith("./") else ref[0]
        p = os.path.normpath(os.path.join(self.base, rel))
        where = f"{os.path.basename(self.src)}:{self.line(i)}"
        if not p.startswith(self.assets) or not os.path.isfile(p):
            (self.outside if not p.startswith(self.assets) else self.missing).setdefault(rel, where)
            return False
        self.used[p] = os.path.getsize(p)
        css = self.css(open(p, encoding="utf-8").read(), os.path.dirname(p), os.path.relpath(p, self.base))
        css = re.sub(r"</(style)", r"<\\/\1", css, flags=re.I)
        media = f' media="{a["media"]}"' if a.get("media") else ""
        self.pieces += [(f"<style{media}>\n", "", 0, "tag"), (css, os.path.relpath(p, self.base), 1, "css"), ("\n</style>", "", 0, "tag")]
        return True

    def css(self, css, css_dir, origin):
        def rep(m):
            ref = m.group(2).strip()
            if ref.startswith(("data:", "http:", "https:", "//", "#")):
                return m.group(0)
            path, _, frag = ref.partition("#")
            path = path.split("?")[0]
            p = os.path.normpath(os.path.join(css_dir, path))
            where = f"{origin}:{css.count(chr(10), 0, m.start()) + 1}"
            if not p.startswith(self.assets):
                self.outside.setdefault(os.path.relpath(p, self.base), where)
                return m.group(0)
            if not os.path.isfile(p):
                self.missing.setdefault(os.path.relpath(p, self.base), where)
                return m.group(0)
            self.used[p] = os.path.getsize(p)
            return f"url({data_uri(p)}{'#' + frag if frag else ''})"
        return re.sub(r"""url\(\s*(["']?)([^"')]+)\1\s*\)""", rep, css)

    def script(self, m, deferred):
        """An external <script src="assets/..."> -> inline pieces; False when it stays as it is."""
        a, raw = attrs(m.group(2))
        ref = self.asset_attr(a.get("src"))
        if not ref:
            return False
        rel = ref[0][2:] if ref[0].startswith("./") else ref[0]
        p = os.path.normpath(os.path.join(self.base, rel))
        where = f"{os.path.basename(self.src)}:{self.line(m.start())}"
        if not p.startswith(self.assets) or not os.path.isfile(p):
            (self.outside if not p.startswith(self.assets) else self.missing).setdefault(rel, where)
            return False
        self.used[p] = os.path.getsize(p)
        origin = os.path.relpath(p, self.base)
        js = re.sub(r"</(script)", r"<\\/\1", open(p, encoding="utf-8").read(), flags=re.I)
        js = self.literals(js, origin, 1)
        keep = "".join(" " + r for k, r in raw.items() if k not in DROP_ON_INLINE)
        out = [(f"<script{keep}>\n", "", 0, "tag"), (js, origin, 1, "js"), ("\n</script>", "", 0, "tag")]
        module = (a.get("type") or "").lower() == "module"
        if "defer" in a and "async" not in a and not module:
            deferred += out                                   # inline scripts ignore defer: run it after the page instead
        else:
            self.pieces += out
        return True

    def render(self):
        html, name, pos, deferred = self.html, os.path.basename(self.src), 0, []
        for m in TOKEN.finditer(html):
            if m.start() > pos:
                self.pieces.append((html[pos:m.start()], name, self.line(pos), "text"))
            pos, tok, ln = m.end(), m.group(0), self.line(m.start())
            if tok.startswith("<!--"):
                self.pieces.append((tok, name, ln, "comment"))
            elif m.group(1):
                kind = m.group(1).lower()
                if kind == "script" and self.script(m, deferred):
                    continue
                open_end = m.start(3) - m.start()
                head, body = tok[:open_end], m.group(3)
                if kind in ("script", "style"):
                    head, body = self.literals(head, name, ln, tag=True), self.literals(body, name, self.line(m.start(3)))
                self.pieces += [(head, name, ln, "tag"), (body, name, self.line(m.start(3)), "raw"), (m.group(4), name, self.line(m.start(4)), "tag")]
            elif tok[:5].lower() == "<link" and tok[5:6] in (" ", "\t", "\n", "\r", "\f", "/", ">") and self.link(tok, m.start()):
                continue
            else:
                self.pieces.append((self.literals(tok, name, ln, tag=True), name, ln, "tag"))
        if pos < len(html):
            self.pieces.append((html[pos:], name, self.line(pos), "text"))
        if deferred:
            for k in range(len(self.pieces) - 1, -1, -1):
                text, origin, ln, kind = self.pieces[k]
                j = text.lower().rfind("</body") if kind == "text" else -1
                if j >= 0:
                    self.pieces[k:k + 1] = [(text[:j], origin, ln, kind)] + deferred + [(text[j:], origin, ln + text.count("\n", 0, j), kind)]
                    break
            else:
                self.pieces += deferred
        problems = []
        for text, origin, ln, kind in self.pieces:
            if kind == "comment" or not origin:
                continue
            scan(text, origin, ln, self.left)
            for rx, what in EXTERNAL:
                for e in rx.finditer(text):
                    problems.append(f"{origin}:{ln + text.count(chr(10), 0, e.start())}: {what}: {text[e.start():e.start() + 90]!r}")
        reported = set(self.missing) | set(self.outside)
        def known(tok):
            tok = tok.replace("\\/", "/")
            return tok in reported or any(k.startswith(tok + " ") for k in reported)
        self.left = list(dict.fromkeys(x for x in self.left if not known(x[2])))
        return "".join(p[0] for p in self.pieces), problems


def build(src, out, allow_external=False):
    b = Build(src)
    html, problems = b.render()
    if b.missing:
        print("MISSING assets (fix the path or add the file):", *[f"{r}  ({w})" for r, w in sorted(b.missing.items())], sep="\n  ", file=sys.stderr)
    if b.outside:
        print("OUTSIDE assets/ (only files inside the show's assets/ folder are inlined):", *[f"{r}  ({w})" for r, w in sorted(b.outside.items())], sep="\n  ", file=sys.stderr)
    if b.left:
        print("UNRESOLVED assets/ paths, still in the output after inlining, so the built show would miss them.\n"
              "  Write each as one complete literal path (\"assets/logos/acme.webp\"); for a logo wall, paste logos.json\n"
              "  into the SHOW script, its \"src\" values are such paths. Reword text or comments that mention assets/.",
              *[f"{o}:{ln}: {tok}  ({why}): …{snip}…" for o, ln, tok, snip, why in b.left], sep="\n  ", file=sys.stderr)
    if problems and not allow_external:
        print("EXTERNAL resources (the show must run offline; download them into assets/):", *problems, sep="\n  ", file=sys.stderr)
    if b.missing or b.outside or b.left or (problems and not allow_external):
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    data = html.encode("utf-8")
    with open(out, "wb") as f:
        f.write(data)
    gz = len(gzip.compress(data, 9, mtime=0))
    print(f"wrote {out}: {len(data):,} bytes, gzip -9 {gz:,} bytes, {len(b.used)} assets inlined")
    for p, n in sorted(b.used.items(), key=lambda x: -x[1])[:10]:
        print(f"  {n:>10,}  {os.path.relpath(p, b.base)}")


def strip(src, out):
    s = open(src, encoding="utf-8").read()
    s = DATA_URI.sub(lambda m: f"data:{m.group(1)};base64,…({len(m.group(3)) * 3 // 4:,} B)", s)
    s = re.sub(r'\sd="[^"]{200,}"', ' d="…"', s)
    open(out, "w", encoding="utf-8").write(s)
    print(f"wrote {out}: {len(s):,} characters")


def unbundle(src, outdir):
    s = open(src, encoding="utf-8").read()
    adir = os.path.join(outdir, "assets", "inline")
    os.makedirs(adir, exist_ok=True)
    count, kept = {}, [0]

    def rep(m):
        ext = EXT.get(m.group(1).lower())
        try:
            raw = base64.b64decode(m.group(3), validate=True)
        except ValueError:
            raw = None
        # extract only what build writes back identically: known type, no parameters, canonical base64
        if raw is None or not ext or m.group(2) or m.group(0) != f"data:{MIME[ext]};base64,{base64.b64encode(raw).decode()}":
            kept[0] += 1
            return m.group(0)
        name = hashlib.sha1(raw).hexdigest()[:12] + ext
        path = os.path.join(adir, name)
        if not os.path.exists(path):
            open(path, "wb").write(raw)
        count[name] = len(raw)
        return "assets/inline/" + name

    parts, pos = [], 0
    for m in TOKEN.finditer(s):                               # only where build inlines: tags, script and style bodies
        parts.append(s[pos:m.start()])
        tok = m.group(0)
        parts.append(tok if tok.startswith("<!--") or (m.group(1) or "").lower() in ("textarea", "title") else DATA_URI.sub(rep, tok))
        pos = m.end()
    parts.append(s[pos:])
    out = os.path.join(outdir, "show.html")
    open(out, "w", encoding="utf-8").write("".join(parts))
    print(f"wrote {out} ({len(''.join(parts)):,} characters) and {len(count)} files in {adir} ({sum(count.values()):,} bytes)"
          + (f"; {kept[0]} data: URIs kept inline (parameters or a type build would write differently)" if kept[0] else ""))
    b = Build(out)
    again, _ = b.render()
    orig = open(src, "rb").read()
    if not (b.missing or b.outside or b.left) and again.encode("utf-8") == orig:
        print(f"check: build turns {out} back into the same bytes as {src}")
    else:
        a = again.encode("utf-8")
        i = next((k for k in range(min(len(a), len(orig))) if a[k] != orig[k]), min(len(a), len(orig)))
        line = orig.count(b"\n", 0, i) + 1
        print(f"WARNING: build of {out} would not reproduce {src} byte for byte (first difference at line {line}); "
              "compare before relying on it", file=sys.stderr)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 3 or args[0] not in ("build", "strip", "unbundle"):
        sys.exit(__doc__)
    cmd, a, b = args
    if cmd == "build":
        build(a, b, "--allow-external" in sys.argv)
    elif cmd == "strip":
        strip(a, b)
    else:
        unbundle(a, b)
