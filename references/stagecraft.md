# Stagecraft

For a show watched from up to 30 m on a projector while someone talks. **Hard limits**, Content included (contract, licences, official source): breaking one breaks the show. **Defaults**, One space and Motion budget included: a starting calibration, changed per deck or room. **Lessons**: each with its reason.

## Hard limits

- The screen supports the speaker: it shows what the audience must see to follow, remember or act on; the rest of the speech goes into the notes.
- Legibility on the 1920×1080 stage: body ≥ 32 px, labels ≥ 26 px. One exception (the other is an approved slide, Content) is fine print a licence, contract or law requires (source lines, disclaimers, trademark notes): verbatim and complete beside what it belongs to, marked `data-legal`, ≥ 18 px, and exempt from nothing else; concept.md and the handover name its size and rule. It must survive a photo of the screen (a 1280×800 projector shows 18 px as 12 pixels). Text merely set small is not fine print.
- Contrast, as projectors wash out pale tints (more so in daylight): text ≥ 7:1 for body and labels, ≥ 4.5:1 at display sizes (≥ 72 px); strokes ≥ 3 px; weights ≥ 400 at body size; no hairline grids. LED walls run bright: no large pure-white areas in a dark room.
- Screen factor `f` = min(1, the screen's aspect ratio ÷ 16/9) × min(1, 30 m ÷ the distance to the farthest seat), as a narrower screen fits the stage to its width and distance shrinks everything: 4:3 gives 0.75 (labels ≥ 35 px), 40 m another × 0.75. Divide the size limits by `f` and set it in qa.md's layout scan. A screen wider than 16:9 shows bars at the sides: tell the user.
- Content stays inside a safe area (keystone and overscan crop the edges). Decoration may bleed, marked `aria-hidden="true"` so screen readers and the layout scan skip it.
- One moving focal point at a time.
- Nothing flashes more than three times in any one second (WCAG 2.3.1): no one can switch on reduced motion for the big screen.
- QR codes, scanned from the seats: static, dark on white, quiet zone ≥ 4 modules, ≥ 300 stage px ÷ `f`.
- Each click visibly changes something at once; Back restores the previous state exactly.
- Only the speaker's click advances the talk; a pre-show loop runs on its own until the first click.
- Every beat has an end state that carries its message alone: under `prefers-reduced-motion` only that shows (engine.md, Reduced motion).
- Offline: fonts, images and scripts inside the file; `<skill>/scripts/build.py` refuses network links.

## Content

- The deck's language, register and inclusive forms; numbers, dates and times in its locale (1.200 in German, 1,200 in English).
- Names, titles and companies as the official source spells them. Where the audience must go: weekday, date, time, room.
- Volatile facts (attendee numbers, rooms, wifi, sponsor lists, times) change until the last day: easy to find in `show.html`, listed in the handover.
- Sponsor tiers as the contract defines them, the list as the official site has it (it changes late).
- Portraits carry no other company's logo (on stage it reads as an endorsement): crop it out.
- Material under its owner's usage rules (analyst graphics such as a Gartner Magic Quadrant, award badges, logos with a brand guide) appears exactly as supplied: the original file byte-unchanged (no re-encode, resize or crop, so never through `<skill>/scripts/images.py`; getting it: sources.md, PDF), whole at its own aspect ratio, nothing recoloured, redrawn, filtered, shadowed or moving inside it, its caption, source lines and disclaimer verbatim. Design the scene around it. It may fade in whole with its scene (`data-in="fade"`, not inside a `data-step`, which slides it); on a click, fade it with plain CSS on the scene's step class: `#s-x .fig{opacity:0;transition:opacity .9s} #s-x.s1 .fig{opacity:1}` with `data-steps="1"`.
- When the terms cover a whole approved slide (it may be shown only in that format), that slide is the scene, unchanged: rendered from its deck page at twice the stage resolution (sources.md, PDF), one `<img>` that fills the stage (`position:absolute; inset:0; width:100%; height:100%; object-fit:contain`) marked `data-legal`, which exempts it from the safe area and the size limits; nothing added, no entrance beyond a plain fade of the whole slide (`data-in="fade"`), and no ambient layer showing through it: hide those layers before the fade starts. Intake confirms the deck's slide is that slide, unadapted.
- Brand font files only when the user supplies them and their licence allows web embedding (the file carries its fonts to every machine); else the closest Google Font.

## Defaults

- On screen: the scene's one message in its shortest form, plus what the audience must note or act on (names, times, rooms, URLs).
- Type: one scale of 4–5 sizes for the whole show, headlines ≥ 72 px; display sizes tracked −0.02 to −0.05 em, leading 0.9–1.0; tabular figures. ≤ ~25 words visible at once; display lines ≤ ~34 characters.
- Colour: tokens per tone (`--bg`, `--fg`, `--fg-soft`, `--acc`, …) for every colour but QR codes. De-emphasise text by size, weight or `--fg-soft` (which meets the contrast limit too), not opacity (it usually breaks it); dim graphics instead.
- Space: multiples of 8 px; safe area 140 px left and right, 96 px top, 90 px bottom; one anchor the whole show keeps (a left edge, a centre line, a grid), so the eye knows where to look after each click.
- Depth follows the tone: shadows on light backgrounds; brightness or a glow on dark ones.
- People of one group (speakers, hosts, team) share one treatment: frame shape, crop height (faces in the upper third), backdrop, order of name, role and title. Look at each photo at full size first; crop out badges, lanyards and half-cut people.
- Sponsor walls: equal perceived weight per tier, alphabetical (case-insensitive) unless the contract sets an order, the list in a data array (a change is a one-line edit).
- Entrances in reading order (headline, key fact, supporting text), staggered 100–150 ms: a scene reads within ~1.5 s of the click; a narrative beat (typing, a formation) may take up to ~3.5 s. Everything but the beat enters quietly, then holds still.
- Steps reveal what the speaker is about to say, each click earning its place; many clicks in one scene suggest a split.
- Images: photos ≤ 1600 px WebP; logos each in one box on one backing, in the version that reads on it, balanced by area and by eye. `<skill>/scripts/images.py` fits logos into boxes and scales photos down; it never crops or balances: crops come from CSS (`object-fit`, `object-position`) or by hand. A host may cap the file size (hosting.md).

## One space

Name in concept.md what makes the show one space: an ambient layer that persists and re-arranges between scenes (positions, scale, density, formation, over about 2 s), one canvas the camera travels, a typographic frame, or deliberate stillness. Derive it from the brand (a logo shape, its pattern, its colours); with a weak brand, particles that carry meaning (one per session, per country). A tone change reads as a new chapter: change tones sparingly; returning to the opening's tone is one way to close.

## Motion budget

Calm is the default: a show reads as too busy through amplitude and the number of things moving at once, not through speed. At a livelier event (a party, a launch) beats may grow in amplitude and tempo; text entrances outside a beat and logo and portrait walls keep the calm budget at any energy level, growing only when the user asks and every logo and name still reads.

| element | calm budget |
|---|---|
| entrance offset | the engine's: 24 px up or down, 40 px sideways, .25 em per split letter; ≤ 3 px blur, scale ≥ .92, no rotation on text |
| easing | ease-out; no overshoot on content (one on a beat is fine) |
| idle motion on content (bob, sway) | ≤ 6 px amplitude, period ≥ 10 s, decorative items only |
| logo and portrait walls | entrance, then still or a ≤ 4 px slow wave |
| ambient layer | rotation periods ≥ 2 min, drift ≤ 30 px, low contrast behind text |
| pre-show loop | the slowest scene: it plays for 30 minutes or more |

## Lessons

- Outline text on variable fonts: `-webkit-text-stroke` draws every internal contour overlap as a crossing line. Use `color: var(--bg); -webkit-text-stroke: <2× width> <colour>; paint-order: stroke fill`.
- Measure text-dependent layouts after `document.fonts.ready`: before it, the fallback font's metrics apply.

## Rehearsal checklist (for the handover)

- Run the built file on the presenting machine: real clicker, real resolution, Chrome fullscreen, the room's light. Fullscreen needs a key press in the window (F), or Chrome started with `--start-fullscreen` or `--kiosk`.
- Press every clicker key once: next, back, blank (B or `.`), present (F5).
- P opens the presenter view; move the audience window to the projector and press F there.
- Scan every QR code with a phone from the back row, on the projected screen.
- Sleep, notifications and updates off (the wake lock covers sleep only from the local file or https; otherwise, on macOS, `caffeinate -d` while presenting); power connected; a copy on a USB stick.
- Before doors open, start at the pre-show loop, if any: `<file>#<scene-id>`.
- The speaker runs the talk once at full pace with the notes; then walk the show once backwards.
