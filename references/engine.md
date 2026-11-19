# Engine contract

`<skill>/assets/engine.html` is the reference engine: two ENGINE blocks (style, script) every show keeps, and SHOW parts (style, scene markup, a script defining `SHOW`) each show replaces. Both ENGINE header comments carry the version, `ENGINE YYYY-MM-DD` (`.2` for a second change that day).

- An engine bug in a show: fix its ENGINE blocks, add a local suffix to both version comments (`ENGINE 2026-11-18+local`) and tell the user, who may report it upstream. When the user maintains the skill, fix the skill's copy instead (bump both comments, add a line under Versions) and refresh the show from it.
- A refresh replaces each ENGINE block whole, header comment to closing tag; a `+local` fix the newer engine lacks goes back in.

## Scenes

```html
<section class="scene" id="s-welcome" data-id="welcome" aria-label="Welcome" data-tone="dark" data-steps="2"> … </section>
```

- Direct children of `#stage`, in show order; ambient layers go into `#stage` before the first scene.
- `data-id`: unique, URL-safe; deep links `#welcome`, `#welcome/2`. `id="s-<data-id>"` hooks the scene's own CSS (`#s-welcome .x`).
- `aria-label`: the title in the presenter view and the notes overlay.
- `data-tone` is mirrored to `<html data-tone>`; define `--bg`, `--fg`, `--acc` (progress bar) per tone. Tones crossfade in 1.2 s (the scene the show opens at shows its tone at once); bars on other aspect ratios take the scene's background colour. `<html data-scene>` holds the current id.
- `data-steps`: optional (default: the highest `data-step` inside); set it only for steps without an element of their own (CSS on `.s1`).
- Own attributes (`data-fx`, `data-layout`): read them in `SHOW.onScene`.
- Entering, a scene shows at once, above the leaving one going forward: content without `data-in` or `data-step` appears at the click (a full-bleed backdrop too).
- Leaving, the scene fades out whole in 0.5 s. Its own `opacity` and `transition` belong to the engine: a pan or slower fade set there makes it cut, or linger until hidden at 0.9 s, above the entering scene going back. Pan or fade an inner wrapper.

## Attributes

| attribute | effect |
|---|---|
| `data-in` | enters with the scene, or with its step inside a `data-step`: `up` (default), `left`, `right`, `down`, `scale`, `fade`; `fade` also leaves without lift or blur |
| `data-d="ms"` | extra delay, inherited inside (split letters, counters, typers) but not by a `data-step` |
| `data-split` | letters cascade in; inner markup kept, the element gets an `aria-label` |
| `data-step="n"` | hidden until step n; appears at once on the click unless it has its own `data-d` |
| `data-exit` | lifts and blurs while the scene fades out (for elements animated by your own CSS) |
| `data-ambient` | under reduced motion: CSS animations stop, transitions change only opacity |
| `data-count="1200"` | counts up from 0 when it enters or its step appears; `data-decimals`, `data-dur` (ms); `SHOW.locale` format |
| `data-type` or `data-type="text"` | types its text when it enters or its step appears; `data-speed` (ms per character) |
| `data-countdown="2030-01-01T09:00:00+01:00"` | live `m:ss`, `h:mm:ss` or `Nd hh:mm:ss`; then the text of `data-done` and class `done` |
| `data-clock` | the current time, HH:MM |

An element takes `data-in` or `data-step`, not both: wrap one in the other. Everything inside a `data-step` (`data-in`, `data-split`, `data-type`, `data-count`) starts when the step appears; delays there count from the click, and an inner `data-d` replaces the step's. A scene opened at a step (Back, a deep link, `STAGE.go(id, n)`) brings the steps up to n in with it, after `--enter`. A chat answer typed on the click: `<div class="bubble" data-step="1"><p data-type>…</p></div>`.

State classes: `active` (visible), `on` (entered: entrances as `.scene.on .x`, in a step as `[data-step].shown .x`), `leaving` (about 0.9 s), `s1` … `sN` (step ≥ n), plus `--step`; a visible `data-step` carries `shown`. A step that moves things is plain CSS: `#s-pair .left{…} #s-pair.s1 .left{transform:translateX(150px)}`. Put delays on entering states only (`.on`, `.shown`), so Back and leaving act at once.

The engine owns `opacity` and `transform` of every `data-in` and `data-step` element, and `filter` of a `data-in` one: it overwrites a placement transform there (a centring `translateX(-50%)` is gone once the element enters), and scene CSS with an ID that sets them breaks the entrance. Place such an element without a transform; give opacity, transform and filter to a wrapper inside or around it.

`--enter` is 380 ms before the first entrance (while the old scene fades), 0 on a step shown by a click and inside it; `--ease` is the easing. Use `var(--enter)` in your own entrance delays, so they follow the same rule.

## SHOW

```js
const SHOW = {
  locale: 'de-DE',                        // numbers, clock
  ui: { … },                               // chrome strings in the deck's language
  notes: { welcome: 'Text for the presenter.\nClick 1: …' },
  hooks: { welcome: { enter(el){}, step(el, n){}, leave(el){} } },
  onScene(scene, prev){},                  // scene = { el, id, title, steps }; prev is null at start
  onResize(scale){},                       // after every fit, e.g. canvas size
  onTick(now){}                            // every second, e.g. labels like "starts in"
};
```

- `ui`: every chrome string of the engine's `UI` defaults (`noWake` is the presenter's warning while no screen wake lock is held; `keys` the help table as `[[action, keys], …]`), translated into the deck's language.
- The SHOW script runs before the engine: generate data-driven markup there (walls, timelines, packed circles), `data-step` and `data-in` included. Keep the data in the script (paste lists such as `logos.json`): a `fetch()` resolves after the engine has counted the steps, and the build can't inline paths in a fetched file.
- Hooks start timers and loops in `enter`, stop them in `leave`. Each entry runs `enter(el)` as the entrance starts, then `step(el, n)` with the step the scene opens at (0, its last via Back, or a deep link's). Every click inside the scene runs `step(el, n)`, back too: n is the state to show, not "one more". `leave(el)` runs as the scene starts leaving; `enter` and `leave` come in pairs (a scene left before its entrance started gets neither). `SHOW.onScene` runs at once on every scene change, before `enter`.
- The presenter window runs the same file, hooks and ambient layers included, so its preview matches the stage. The engine mutes every `<audio>` and `<video>` there (`new Audio()` too; to hear one, set `muted = false` once its `play()` resolves); any other one-off effect (Web Audio, a request, a heavy canvas loop) skips there: `if (STAGE.presenter) return;`. CSS can use `body.presenter`. Sound plays only in a window that has had a click or key press: press F in the audience window before the show.
- `onResize(scale)` runs after every fit: size a canvas `1920 × scale × dpr` by `1080 × scale × dpr` (dpr = `devicePixelRatio`, at most 2) and draw in stage coordinates via `setTransform(scale × dpr, 0, 0, scale × dpr, 0, 0)`, as `<skill>/assets/fx.js` does.

## Reduced motion

Under `prefers-reduced-motion: reduce` the engine fades entrances, steps and split letters (a word's letters together) and shows counters and typers final. The show's part:

- JS motion (hooks, canvas loops, ambient sketches) checks `STAGE.still` and holds a still frame: a formation appears in place, nothing drifts.
- Elements with CSS animations or transitions of their own carry `data-ambient`: the engine stops the animations and narrows the transitions to opacity (inside them too), so ambient shapes land at once.
- A pre-show loop changes its panels by fade only: from a hook timer, not a CSS animation, the panels marked `data-ambient`. A still title scene can serve as the pre-show instead.

## STAGE (engine API for hooks and QA)

`STAGE.scenes` (`[{id, title, steps}]`), `STAGE.go(indexOrId, step)`, `STAGE.next()`, `STAGE.prev()`, `STAGE.state()` → `{i, id, step, steps}`, `STAGE.scale`, `STAGE.still`, `STAGE.presenter` (true in the presenter window). Screen pixels ÷ `STAGE.scale` = stage pixels: on a CSS 3D scene, place 2D overlays (pins, labels) from `getBoundingClientRect()` this way on every frame.

## Chrome

- Keys, as the help overlay (? or H) lists them: they cover what clickers send (PageUp/PageDown, arrows, B or `.` to black out until any other key, F5 or Esc); F5 enters fullscreen and never reloads; a click goes on, a click on the left fifth back; a number then Enter jumps; N shows the notes overlay.
- Presenter view: P opens `?presenter=1` in a second window: live stage, elapsed time (click to reset), clock, current and next step, notes. The windows drive each other by `postMessage`, also from `file://`; the audience pairs only with the presenter it opened (no other page can drive it), and a reloaded window takes position and black screen from the other.
- Cursor, toolbar and progress bar hide after 2.5 s without mouse movement. A screen wake lock is requested at load and whenever the page shows again; only a secure context has one (`file://`, https, localhost; not plain `http://`), and the presenter view says when none is held.

## Versions

Newest first, one line per change: what a show gains from a refresh, and what it must change to keep working.

- `2026-11-18`: first public release.
