# QA

Run every check against the built file in `dist/`, not against `show.html`.

## Setup

QA needs a browser you can drive: run JS in the page and read the result, take screenshots, resize the viewport, emulate reduced motion, and reach a second window the page opens. Use your own browser tool when it does all of this; otherwise a short Playwright for Python script, run with `<skill>/run python3`, that launches Chrome with `p.chromium.launch(channel="chrome")`, or the bundled Chromium with `p.chromium.launch()` where Chrome is missing. On Debian or Ubuntu without Chromium's system libraries, `<skill>/run python3 -m playwright install --with-deps chromium` adds them through apt; ask the user first (it installs system packages as root), then run it as yourself, Playwright asks for sudo; where your shell can't answer the password prompt, ask the user to run it in a terminal. Elsewhere, use the package manager.

- Open `file://<workspace>/dist/<slug>.html?v=<n>` at 1920×1080, raising `v` after every build to defeat the cache. Only when your browser tool refuses `file://`, serve it in the background, `<skill>/run python3 -u -m http.server 0 --bind 127.0.0.1 --directory dist` (it prints the free port it picked), open `http://127.0.0.1:<port>/<slug>.html?v=<n>`, and stop the server afterwards.
- The snippets below are plain page JS: evaluate them as written, with the screen factor in the layout scan's first line. The comment on each `return` is the passing result.
- Screenshots are scratch: keep them in a temporary folder outside the workspace, and move any your tool saves elsewhere (some write into the current folder) there.

## 1. Screenshots: the design review

For every scene and step, evaluate `async () => { STAGE.go('<id>', <step>); await new Promise(r => setTimeout(r, 2600)); }` (longer after a slow beat), then screenshot at once as `<NN>-<id>-<step>.png`. Wait inside the evaluated JS: between tool calls a headless page can stop producing frames, freezing entrances half-way. Make contact sheets, `<skill>/run python3 -I <skill>/scripts/images.py sheet <shots>/*.png <shots>/sheets/all.png` (`<shots>`: your screenshot folder), then look at every image, at full size wherever its cell is too small to judge:

- Only what the audience must see to follow, remember or act on: the scene's message from concept.md, readable at a glance, the rest of the speech in `SHOW.notes`?
- Readable from the back row (an approved slide is exempt: stagecraft.md, Content)? Body text ≥ 32 px ÷ `f` (the layout scan catches it only in blocks of more than 12 words); contrast?
- Overlaps, cut-off text, crowded corners, uneven margins?
- Crops: faces, badges, logos? Material under usage rules whole and untouched?
- Each QR code static, dark on white, ≥ 300 stage px ÷ `f`, with a quiet zone of ≥ 4 modules?
- One moving focal point, everything else calm?
- Put each scene's screenshot next to the page pictures of its source slides (concept.md's source slides column); where the layout is recognisable and concept.md gives no reason to keep it (a full-bleed photo, a diagram the speaker points into), redesign the scene.

Also:

- A beat that unfolds: screenshots 300, 900 and 1800 ms after the click.
- Back: in a scene with steps, reach each step n below the last from step n + 1, `async () => { const w = ms => new Promise(r => setTimeout(r, ms)); STAGE.go('<id>', <n + 1>); await w(2600); STAGE.prev(); await w(2600); }`; its screenshot matches the forward one.
- A pre-show loop changes its panels on its own: screenshot every panel (wait inside the evaluated JS until it shows), and run the layout scan and the contrast check once per panel: start on another scene, put `STAGE.scenes.filter(x => x.id === '<id>')` in place of `STAGE.scenes`, and raise the wait to when that panel shows.
- Load frame: open a fresh page at `#<id>`, evaluate a 300 ms wait, screenshot: nothing but the scene's own entrances may be on their way in (the usual find: an ambient layer sweeping in from a corner).

QR codes: `<skill>/run python3 -I -c 'import sys,zxingcpp,PIL.Image as I; [print(b.text, "at", b.position) for b in zxingcpp.read_barcodes(I.open(sys.argv[1]))] or sys.exit("no QR code found")' <shots>/<NN>-<id>-<step>.png` must print the address content.md names. A code with a logo must also decode from a half-size and a blurred copy (a projector softens it): `<skill>/run python3 -I -c 'import sys,PIL.Image as I,PIL.ImageFilter as F; i=I.open(sys.argv[1]); i.resize((i.width // 2, i.height // 2)).save(sys.argv[2]); i.filter(F.GaussianBlur(1.5)).save(sys.argv[3])' <shots>/<NN>-<id>-<step>.png <shots>/qr-half.png <shots>/qr-blur.png`. Without zxing-cpp (Python 3.9 on Linux ARM), the rehearsal phone scan is the only decode test.

Walk at speaking pace through the screenshots in order: read a scripted talk's `SHOW.notes` aloud at the speaker's pace (about 130 words a minute unless intake says otherwise), and give a free speaker's sections the minutes intake recorded. Each click comes where its words need it, each beat lands on the words it shows, no scene sits silent or runs long, the talk fits the slot and builds toward concept.md's peak. Fix the order or the steps; when the speaker's own words overrun the slot, tell the user.

## 2. Scripted checks

Navigation walk, forwards and back; `dead` lists the clicks that change nothing:

```js
async () => {
  const st = () => { const s = STAGE.state(); return s.id + '/' + s.step; }, settle = () => new Promise(r => setTimeout(() => requestAnimationFrame(() => requestAnimationFrame(r)), 50));
  const dyn = '[data-count],[data-type],[data-countdown],[data-clock]', P = 'opacity visibility display transform translate scale rotate filter clip-path color background-color background-image fill stroke-dashoffset font-size box-shadow border-color left top width height'.split(' ');
  const look = () => { document.getAnimations().forEach(a => { try { a.finish(); } catch (e) { a.currentTime = 0; } });
    return [...document.querySelectorAll('.scene.on, .scene.on *')].map(e => { const c = getComputedStyle(e), d = e.closest(dyn) || e.querySelector(dyn);   // counters, typers: own changes
      return P.slice(0, d ? -2 : 99).map(p => c.getPropertyValue(p)) + (d ? '' : [...e.childNodes].map(n => n.nodeType === 3 ? n.data : '').join('')); }).join('|'); };
  STAGE.go(0, 0); await settle(); const fwd = [], dead = []; let last = '';
  for (let k = 0; k < 999; k++) { const now = look(); fwd.push(st()); if (STAGE.state().step && now === last) dead.push(st()); last = now; const b = st(); STAGE.next(); if (st() === b) break; await settle(); }
  const back = []; for (let k = 0; k < 999; k++) { back.push(st()); const b = st(); STAGE.prev(); if (st() === b) break; }
  return { fwd, symmetric: JSON.stringify(fwd) === JSON.stringify(back.reverse()), dead };   // symmetric: true, each scene/step once in fwd; dead: [] (a canvas-only step: see its screenshot)
}
```

Layout scan over every scene and step, in stage pixels: text cut by the stage edge or by a box that hides overflow, overlapping blocks of text, text and pictures outside the safe area, text below 26 px ÷ `f`, body text (a block of more than 12 words) below 32 px ÷ `f`, fine print (`data-legal`) below 18 px ÷ `f`, typers still typing, a scene that moved on without a click, broken images. `legal` lists all fine print and every approved slide (a `data-legal` picture whose box is the stage, exempt from the safe area) for review. It skips decoration marked `aria-hidden="true"` and text parked completely outside the stage or its box (a later step; masked digits of an odometer: a mask's box is the font's content box, about 1.32 em tall whatever the line-height).

```js
async () => {
  const f = 1, min = 26 / f, body = 32 / f, fine = 18 / f, safe = { l: 140, t: 96, r: 1780, b: 990 };   // f: screen factor; safe: safe area
  const wait = ms => new Promise(r => setTimeout(r, ms)), stage = document.getElementById('stage'), out = [], legal = [];
  for (const sc of STAGE.scenes) for (let s = 0; s <= sc.steps; s++) {
    STAGE.go(sc.id, s); await wait(2600);
    const where = sc.id + '/' + s, z = STAGE.state(), scene = document.querySelector('.scene.on'), k = STAGE.scale, S = stage.getBoundingClientRect();
    if (z.id !== sc.id || z.step !== s) out.push([where, 'moved on its own to ' + z.id + '/' + z.step]);
    const memo = new Map(), css = el => memo.get(el) || memo.set(el, getComputedStyle(el)).get(el);
    const op = x => { let o = 1; for (; x && x !== stage; x = x.parentElement) o *= +css(x).opacity; return o; };
    const px = r => ({ l: (r.left - S.left) / k, t: (r.top - S.top) / k, r: (r.right - S.left) / k, b: (r.bottom - S.top) / k });
    const within = (a, c) => a.l >= c.l - 1 && a.r <= c.r + 1 && a.t >= c.t - 1 && a.b <= c.b + 1;
    const apart = (a, c) => a.r <= c.l || a.l >= c.r || a.b <= c.t || a.t >= c.b;
    const name = el => (el.closest('[data-split]')?.getAttribute('aria-label') || el.textContent).replace(/\s+/g, ' ').trim().slice(0, 40);
    const ext = rs => 'x ' + Math.round(Math.min(...rs.map(r => r.l))) + '..' + Math.round(Math.max(...rs.map(r => r.r))) + ' y ' + Math.round(Math.min(...rs.map(r => r.t))) + '..' + Math.round(Math.max(...rs.map(r => r.b)));
    const blocks = new Map(), range = document.createRange(), tw = document.createTreeWalker(scene, NodeFilter.SHOW_TEXT);
    for (let t; (t = tw.nextNode()); ) {
      const el = t.parentElement;
      if (!t.textContent.trim() || el.closest('[aria-hidden="true"]:not([data-split] *)') || css(el).visibility !== 'visible' || op(el) < .1) continue;
      range.selectNodeContents(t);
      const rects = [...range.getClientRects()].filter(r => r.width > 0).map(px);
      if (!rects.length) continue;
      const clips = [[stage, { l: 0, t: 0, r: stage.offsetWidth, b: stage.offsetHeight }]];
      for (let a = el; a !== scene; a = a.parentElement) if (css(a).overflow !== 'visible') clips.push([a, px(a.getBoundingClientRect())]);
      let blk = el; while (blk !== scene && /^(inline|contents)/.test(css(blk).display)) blk = blk.parentElement;
      const B = blocks.get(blk) || blocks.set(blk, { all: [], shown: [], cut: new Map() }).get(blk);
      const size = parseFloat(css(el).fontSize), lg = el.closest('[data-legal]');
      if (lg) B.legal = css(el).fontSize;
      if (size < (lg ? fine : min)) B.font = css(el).fontSize; else if (!lg && size < body) B.body = css(el).fontSize;
      for (const r of rects) {
        const hid = clips.some(([, cb]) => apart(r, cb));   // hidden by one box: no other box cuts it
        for (const [c, cb] of clips) {
          const n = B.cut.get(c) || B.cut.set(c, { in: 0, out: 0, part: 0 }).get(c);
          if (within(r, cb)) n.in++; else if (apart(r, cb)) n.out++; else if (!hid) n.part++;
        }
        B.all.push(r); if (!hid) B.shown.push(r);
      }
    }
    const list = [...blocks], band = r => ({ l: r.l + 1, r: r.r - 1, t: r.t + (r.b - r.t) * .22, b: r.b - (r.b - r.t) * .22 });   // a line's middle band, about cap height
    list.forEach(([el, B], i) => {
      for (const [c, n] of B.cut) if (n.part || (n.in && n.out))
        out.push([where, c === stage ? 'outside the stage' : 'clipped by ' + c.tagName.toLowerCase() + (c.getAttribute('class') ? '.' + c.getAttribute('class').split(' ')[0] : ''), name(el), ext(B.all)]);
      if (B.font) out.push([where, 'font ' + B.font, name(el)]);
      else if (B.body && el.textContent.trim().split(/\s+/).length > 12) out.push([where, 'font ' + B.body + ' for body text', name(el)]);
      if (B.legal) legal.push([where, B.legal, name(el)]);
      if (B.shown.some(r => !within(band(r), safe))) out.push([where, 'outside the safe area', name(el), ext(B.shown)]);
      for (const [el2, B2] of list.slice(i + 1))
        if (B.shown.some(a => B2.shown.some(b => !apart(band(a), band(b))))) out.push([where, 'overlaps "' + name(el2) + '"', name(el)]);
    });
    for (const el of scene.querySelectorAll('img, svg, video, canvas')) { const r = px(el.getBoundingClientRect());
      if (el.matches('img[data-legal]') && within(px(S), r) && within(r, px(S))) legal.push([where, 'approved slide', el.alt]);
      else if (!el.closest('[aria-hidden="true"]') && !el.parentElement.closest('svg') && css(el).visibility === 'visible' && op(el) >= .1 && !apart(r, px(S)) && !within(r, safe)) out.push([where, 'outside the safe area', el.alt || el.tagName.toLowerCase(), ext([r])]); }
    for (const el of scene.querySelectorAll('[data-type]')) if (op(el) >= .1 && el.textContent !== el.dataset.type) out.push([where, 'still typing: wait longer', name(el)]);
  }
  const broken = [...document.images].filter(i => !i.naturalWidth).map(i => i.alt || i.src.slice(0, 60));
  return { out, broken, legal };   // out, broken: [] (or a reason in concept.md); legal: only required fine print and approved slides
}
```

Contrast: the WCAG ratio of every visible text against the background colours under it (alpha and opacity composited), for every scene and step. For text over a picture, a gradient or an ambient layer, sample the pixels behind it in the screenshots.

```js
async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms)), stage = document.getElementById('stage'), out = new Map(), g = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  const lum = layers => { for (const [c, o] of [['#fff', 1], ...layers]) { g.globalAlpha = o; g.fillStyle = c; g.fillRect(0, 0, 1, 1); }
    const [r, gn, b] = [...g.getImageData(0, 0, 1, 1).data].map(v => (v /= 255) <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4); return .2126 * r + .7152 * gn + .0722 * b; };
  for (const sc of STAGE.scenes) for (let s = 0; s <= sc.steps; s++) {
    STAGE.go(sc.id, s); await wait(2600);
    for (const el of document.querySelectorAll('.scene.on *')) {
      const key = el.closest('[data-split]') || el, c = getComputedStyle(el), chain = [];
      if (out.has(key) || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) || el.closest('[aria-hidden="true"]:not([data-split] *)') || c.visibility !== 'visible') continue;
      for (let x = el; x !== stage; x = x.parentElement) chain.unshift(getComputedStyle(x));
      let o = 1; const under = [[getComputedStyle(stage).backgroundColor, 1], ...chain.map(k => [k.backgroundColor, o *= +k.opacity])];
      const ink = el instanceof SVGElement ? c.fill : parseFloat(c.webkitTextStrokeWidth) ? c.webkitTextStrokeColor : c.webkitTextFillColor;
      const a = lum(under), t = lum([...under, [ink, o]]), ratio = Math.floor((Math.max(a, t) + .05) / (Math.min(a, t) + .05) * 10) / 10;
      if (o >= .1 && ratio < 7 && chain.every(k => k.backgroundImage === 'none'))   // over a picture or gradient: screenshots
        out.set(key, [sc.id + '/' + s, (key.getAttribute('aria-label') || el.textContent).replace(/\s+/g, ' ').trim().slice(0, 40), ratio, c.fontSize]);
    }
  }
  return [...out.values()];   // [] or only display-size text at ≥ 4.5
}
```

Flashing: repeating CSS and Web Animations that cycle more than three times a second. Hook timers and canvas loops are outside its view: ask of each whether it switches between light and dark that fast.

```js
async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms)), out = new Map();
  for (const sc of STAGE.scenes) for (let s = 0; s <= sc.steps; s++) {
    STAGE.go(sc.id, s); await wait(1000); const scene = document.querySelector('.scene.on');
    for (const a of document.getAnimations()) {
      const t = a.effect.getComputedTiming(), el = a.effect.target, cycle = t.duration * (/alternate/.test(t.direction) ? 2 : 1) / Math.abs(a.playbackRate);
      const what = (a.animationName || 'script') + ' on ' + el.tagName.toLowerCase() + (el.classList[0] ? '.' + el.classList[0] : '');
      if (t.iterations > 3 && cycle < 1000 / 3 && (el.closest('.scene') || scene) === scene && !out.has(what)) out.set(what, [sc.id + '/' + s, what, Math.round(cycle) + ' ms']);
    }
  }
  return [...out.values()];   // [] (motion that changes no light may stay)
}
```

Exit check, forwards and back: every scene fades out within 0.5 s (going back, the leaving scene sits above the entering one). It fails when scene CSS overrides the scene's own `opacity` or `transition` (engine.md, Scenes), or when heavy painting slows the fade: a wide `drop-shadow` or `blur` on a big image can, in headless Chrome, depending on load. Run it again; when it still fails, bake the shadow into the image or make it smaller (a weak presenting machine stutters too). Going forward it also reports a picture or opaque background that covers the whole stage at the click (not a picture with transparency, such as a frame: it hides nothing): the entering scene shows at once on top, a hard cut; fade it in with `data-in="fade"` (move a scene's own background to an inner element first).

```js
async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms)), N = STAGE.scenes.length, moves = [], bad = [], S = document.getElementById('stage').getBoundingClientRect();
  const op = x => { let o = 1; for (; x.id !== 'stage'; x = x.parentElement) o *= +getComputedStyle(x).opacity; return o; };
  const covers = e => { const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    return r.left <= S.left + 1 && r.top <= S.top + 1 && r.right >= S.right - 1 && r.bottom >= S.bottom - 1 && c.visibility === 'visible' && op(e) > .9
      && (/^(IMG|VIDEO)$/.test(e.tagName) || /url\(/.test(c.backgroundImage) || !/^rgba|\/ 0[.)]/.test(c.backgroundColor)); };
  const solid = async e => { const c = getComputedStyle(e), u = e.tagName === 'IMG' ? e.currentSrc : (/url\("?([^")]+)/.exec(c.backgroundImage) || [])[1];
    if (e.tagName === 'VIDEO' || !u || !/^rgba|\/ 0[.)]/.test(c.backgroundColor)) return true;   // transparency (a frame) hides nothing
    try { const i = new Image(); i.src = u; await i.decode(); const g = new OffscreenCanvas(32, 18).getContext('2d'); g.drawImage(i, 0, 0, 32, 18);
      const d = g.getImageData(0, 0, 32, 18).data; let a = 0; for (let k = 3; k < d.length; k += 4) a += d[k]; return a / 576 / 255 > .9; } catch (x) { return true; } };
  for (let i = 0; i < N - 1; i++) moves.push([i, i + 1]);
  for (let i = N - 1; i > 0; i--) moves.push([i, i - 1]);
  for (const [a, b] of moves) {
    STAGE.go(a, a < b ? STAGE.scenes[a].steps : 0); await wait(1000);
    const old = document.querySelector('.scene.on'), where = STAGE.scenes[a].id + ' → ' + STAGE.scenes[b].id, t0 = performance.now();
    STAGE.go(b, a < b ? 0 : STAGE.scenes[b].steps);
    await wait(150); const early = +getComputedStyle(old).opacity, te = performance.now() - t0, nw = document.querySelector('.scene.active:not(.leaving)');
    const hits = a < b ? [nw, ...nw.querySelectorAll('*')].filter(covers) : [];
    await wait(600 - (performance.now() - t0)); const late = +getComputedStyle(old).opacity;
    for (const cut of hits) if (await solid(cut)) { bad.push([where, 'cuts in: ' + (cut.alt || cut.tagName.toLowerCase() + (cut.classList[0] ? '.' + cut.classList[0] : '')) + ' covers the stage at the click']); break; }
    if (te > 400 || !old.classList.contains('leaving')) bad.push([where, 'sampled too late, run again']);
    else if (late > .05) bad.push([where, 'still at opacity ' + late.toFixed(2) + ' after 0.6 s, then vanishes']);
    else if (early < .01) bad.push([where, 'cuts without fading']);
  }
  return bad;   // [] (or a cut concept.md gives a reason for)
}
```

Material under usage rules: `<skill>/run python3 -I -c 'import base64,hashlib,re,sys; h=lambda b: hashlib.sha256(b).hexdigest(); s={h(base64.b64decode(m)) for m in re.findall(r"data:[^;,]+;base64,([A-Za-z0-9+/=]+)", open(sys.argv[1], encoding="utf-8").read())}; [print(f, h(open(f, "rb").read()) in s) for f in sys.argv[2:]]' dist/<slug>.html assets/<file>...` prints `True` for each file the built file holds byte for byte.

Offline: `() => performance.getEntriesByType('resource').map(e => e.name).filter(u => !/^(data|blob):/.test(u))` returns `[]` (inlined files make no entries, so anything listed came from outside the file, over `file://` and `http://` alike), and the console shows no errors.

Fonts: every family and weight that text uses has a face loaded from the file, and a glyph for every character of that text. A reported font lacks its rule, that weight, or a readable file. A reported character (`"Inter" lacks → (U+2192)`) falls back to another font, often because the Google Fonts subset leaves it out: replace it (an SVG, a character the font has) or fetch a subset that holds it (`<skill>/scripts/fonts.py --subsets`). `document.fonts.check()` answers true in all these cases. Typed text counts once typed.

```js
async () => {
  const want = new Map(), bad = [], generic = /^(serif|sans-serif|monospace|cursive|fantasy|system-ui|ui-[\w-]+|emoji|math)$/, ctx = document.createElement('canvas').getContext('2d');
  for (const el of document.querySelectorAll('body :not(script, style)')) if ([...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) {
    const c = getComputedStyle(el), fam = c.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, ''), f = `${c.fontWeight} 32px "${fam}"`;
    if (!generic.test(fam)) want.set(f, (want.get(f) || '') + [...el.childNodes].map(n => n.nodeType === 3 ? n.textContent : '').join(''));
  }
  for (const [f, t] of want) {
    const w = parseInt(f), fits = x => { const [a, b = a] = x.weight.replace('normal', 400).replace('bold', 700).split(' ').map(Number); return x.status === 'loaded' && a <= w && w <= b; };
    if (!(await document.fonts.load(f).catch(() => [])).some(fits)) { bad.push(f); continue; }
    const cs = [...new Set(Array.from(new Intl.Segmenter().segment(t), x => x.segment))].filter(s => /[^\0-\x7f\s\p{Cc}\p{Cf}]/u.test(s));
    if (cs.length) await document.fonts.load(f, cs.join('')).catch(() => []);
    const px = (font, s) => (ctx.font = font, ctx.measureText(s).width), near = (a, b) => Math.abs(a - b) < .05, big = f.replace('32px', '100px');
    for (const s of cs) {   // fallback shows, or both match bare generics (emoji, CJK)
      const m = px(`${big}, monospace`, s), r = px(`${big}, serif`, s), bare = (g, x) => [w, 400].some(v => near(x, px(`${v} 100px ${g}`, s)));
      const e = `${f.slice(f.indexOf('"'))} lacks ${s} (${[...s].map(ch => 'U+' + ch.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')).join(' ')})`;
      if ((!near(m, r) || bare('monospace', m) && bare('serif', r)) && !bad.includes(e)) bad.push(e);
    }
  }
  return bad;   // []
}
```

## 3. Screens, motion, presenter

- Aspect ratios: 1440×1080 (4:3) and 1920×1200 (16:10), two or three scenes each: bars take the scene colour, nothing is cut.
- Phones, for a hosted show the audience opens on their own devices: 390×844 and 844×390 (Playwright: `viewport`, `is_mobile=True`, `has_touch=True`), two or three scenes each: the stage letterboxes inside the screen, nothing is cut, a tap advances.
- Reduced motion (Playwright: `page.emulate_media(reduced_motion='reduce')`, no reload needed): walk the show; all content visible, counters and typers final, formations and ambient shapes at their end state, each beat's end state carries its message, nothing moves on its own but the pre-show loop's fades. Reset the emulation afterwards.
- Presenter view: press `p` (the second window: Playwright `context.pages`). Press ArrowRight in each window in turn and compare `STAGE.state()` in both; `b` syncs the black screen. `STAGE.presenter` is true only in the presenter, and a show with sound is silent there. Close that window.
