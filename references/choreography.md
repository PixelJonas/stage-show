# Choreography vocabulary

Starting points, not templates: use a pattern only when the content *is* that shape; combine, invert, invent (the best beat often has no name yet). A beat works when its motion is made of the scene's own data: the real count, shares, place.

## Find the shape

| the content is… | it can move as… |
|---|---|
| a count of things | one particle per counted thing, gathering into the number, a key word or the logo (`FX.form`) |
| key figures | big tabular numerals counting up, staggered (`data-count`) |
| shares of a whole | packed circles, area ∝ value, popping in largest first |
| two things that join | two shapes sliding into overlap on a click; the overlap names what they share |
| a schedule | a time axis with lanes; bars grow from their start time; one click per day |
| a place | its real layout, simplified (a floor plan, a site map, a building's floors pulled apart in CSS 3D); pins drop per category per click, the rest dims |
| a person | the portrait in its group's one treatment (stagecraft.md, Defaults) |
| a list of partners | a logo wall rippling in from the centre, then still |
| a call to action | kinetic type at maximum size, letters cascading in (`data-split`), the handle or URL the only other element |
| a prompt, a chat, code | a typed prompt with a blinking cursor, then one answer bubble per click (a `data-step` with a `data-type` inside) |
| music, a party | equaliser bars rising and falling at most three times a second, particles rising |
| waiting time | a countdown (`data-countdown`); wifi and hashtag in the corners |
| a journey, a history | the camera pans along one long canvas, one stop per click |
| a process | a path drawing itself (SVG `stroke-dashoffset`), nodes lighting up per click |
| sizes to compare | shapes scaled by area, side by side, growing from a shared baseline |
| a quote | words appearing in speaking rhythm, the key word in the accent colour |
| a map | a camera flight (scale and translate one big SVG) between locations |
| an agenda | the agenda as chapter divider: the current chapter lit, past ones dimmed |

Compute data-driven layouts (packed circles, timelines, walls) in the SHOW script from a data array, so a changed number re-lays itself.

## Ambient layers

Both sketches follow the scene through `SHOW.onScene`; your own scene attributes (`data-fx`, `data-layout`) choose a formation or arrangement.

Particles that drift or gather into formations come ready-made as `<skill>/assets/fx.js` (version in its header, `FX YYYY-MM-DD`). Use it unchanged when its look fits: it is the tested copy and handles reduced motion. For another look, write your own layer on the same contract (`SHOW.onResize` sizes it, `STAGE.still` holds it at rest). fx.js needs:

- `<canvas id="fx" data-n="240" data-r="4">` as the first child of `#stage`, styled `position:absolute;inset:0;width:1920px;height:1080px;pointer-events:none`: `data-n` dots, at least as many as the largest formation; `data-r` the dot radius in stage px.
- a `--fx` colour per tone; `FX.set` reads it on every scene change.

A formation is any list of `[x, y]` points in stage px. `FX.form(name, make)` registers one for a scene's `data-fx` (`make` returns the points or a promise; the scene drifts until it resolves); `drift` and `none` need none. `FX.text(str, font, n)` samples about `n` points from text in a font, `FX.path(d, x, y, k, n)` from SVG path data (the logo's) at scale `k`, origin `x, y`. In the SHOW script:

```js
FX.form('total', () => FX.text('1200', '800 520px <display family>'));     // the number itself
FX.form('logo', () => { for (let m = TALKS.length; m < TALKS.length + 20; m++) {   // one dot per talk; FX.path returns about m points, so raise m until there are enough
  const p = FX.path(LOGO_PATH_D, 560, 140, 8, m); if (p.length >= TALKS.length) return p.slice(0, TALKS.length); } throw new Error('the logo has room for fewer dots than talks'); });
FX.form('sites', () => SITES.map(s => [s.x, s.y]));                         // any data-driven point list
SHOW.onScene = s => FX.set(s.el.dataset.fx || 'drift');
SHOW.onResize = k => FX.resize(k);
```

Brand shapes that re-arrange per scene: each an absolutely positioned SVG or div with `id="shape-<name>"` and `data-ambient`, its CSS transition doing the travelling; one layout per role, picked per scene with `data-layout`:

```css
.shape{position:absolute;left:0;top:0;opacity:0;transition:transform 2.4s cubic-bezier(.65,0,.25,1),opacity 1.4s ease}   /* hidden until arrange() places it */
```
```js
const LAYOUTS = {                                   // [x, y, scale, opacity] in stage px, one entry per role
  big:   { a: [300, 860, 1.1, 1], b: [1640, 220, 1, 1], c: [1000, 1060, .3, 1] },    // title scenes: the shapes frame the stage
  aside: { a: [1840, 60, .4, 1], b: [1900, 180, .3, 1], c: [1600, -10, .12, 1] },   // text scenes: in a corner, clear of the text
  off:   { a: [2200, 1300, .5, 0], b: [-300, 1300, .5, 0], c: [2100, -200, .2, 0] }  // the scene needs the whole stage
};
function arrange(name, now) {                      // now: place at once, without travelling (page load)
  for (const [id, [x, y, s, o]] of Object.entries(LAYOUTS[name] || LAYOUTS.aside)) {
    const el = document.getElementById('shape-' + id);
    if (now) el.style.transition = 'none';
    el.style.transform = `translate(${x}px,${y}px) translate(-50%,-50%) scale(${s})`;
    el.style.opacity = o;
    if (now) { el.offsetWidth; el.style.transition = ''; }   // commit the jump, then travel again
  }
}
SHOW.onScene = (s, prev) => arrange(s.el.dataset.layout, !prev);   // prev is null at load; both layers: (s, prev) => { FX.set(...); arrange(..., !prev); }
```

A shape can also breathe: an SVG blob path redrawn per frame with small sine offsets on its control points, held still while `STAGE.still`.
