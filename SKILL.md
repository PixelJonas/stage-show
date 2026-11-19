---
name: stage-show
description: Turn a deck (.pptx, PDF, Keynote, slide images) into a stage show, an animated presentation in one offline HTML file the speaker clicks through on the big screen. Use when slides should be animated or redesigned for a talk or event, also from a .pptx (the result is HTML; editing the .pptx itself is another job), or when an existing stage show needs changes.
license: MIT
compatibility: Needs a POSIX shell (Linux or macOS; Windows via WSL) and mise, which installs Python, poppler, tesseract, Pillow, segno, zxing-cpp and Playwright with Chromium (README); without mise, python3 3.9 or newer with Pillow (requirements.txt), poppler 21.11 or newer, tesseract and a browser the agent can drive. Also an agent that can look at images, and network access for fonts and fact checks. The built show runs offline in Chrome or Chromium.
---

# Stage show

A **stage show** re-stages a talk for the big screen behind a speaker. The deck is **raw material**: it supplies facts, words, people, images and brand, never layouts; the one exception is material under its owner's usage rules, which appears as supplied (stagecraft.md, Content). Each scene is designed new around one message, the show builds toward the one thing the audience should leave with, and it is one space, not a row of slides.

Vocabulary: **scene** (one stage state; may merge, split or drop source slides), **step** (a click inside a scene), **beat** (a scene's signature moving moment: at most one per scene, each with its reason; quiet scenes have none), **tone** (a scene's background world; a change marks a chapter), **motion budget** (how much may move: [references/stagecraft.md](references/stagecraft.md)).

Deliverable: `dist/<slug>.html`, one file that runs offline in Chrome on the presenting machine.

## Paths

`<skill>` is the folder that holds this SKILL.md, as an absolute path: write it in place of `<skill>` in every command, quoted when it holds a space or another character the shell treats specially. Put `<skill>/run` before every command that calls python3, a skill script, poppler or tesseract: it runs the command in the current folder with the skill's tools. When a command reports a missing tool or Python module, run `<skill>/install` (without mise: README's manual install, `requirements.txt` included). The workspace is `~/stage-shows/<slug>/` unless the user names one; run every command there (`cd <workspace> && …`: the shell may start elsewhere). A path in backticks is a workspace path unless it starts with `<skill>/`. Every deliverable lands in the workspace; QA screenshots are scratch.

```
source/      the deck as received + its extract (deck.md or deck.txt, pages/, read/, media/, theme.json)
content.md   event, talk, slide inventory, open questions
concept.md   visual system, arc, scene table
show.html    the authored page; assets referenced by literal assets/... paths
assets/      fonts/, logos/, photos/, ...
dist/        the built single file
```

Reference each asset by one complete literal path (`"assets/logos/acme.webp"`), never as base64: the build inlines it.

## Steps

1. **Intake.** Record in `content.md`:
   - the event: name, dates, venue, the slot (start, length, what follows), presenters, language, screen (aspect ratio, projector or LED), the room (distance to the farthest seat, daylight or dark), presenting machine and browser, clicker, venue internet, brand rules, must-keep items (sponsor tiers, legal lines);
   - usage terms for third-party material (analyst firms, award bodies, partner brand guides; where the terms cover a whole approved slide, whether the deck's slide is that slide, unadapted);
   - the talk: the audience, the one thing they should leave with, the speaker's style (scripted or free), their pace, and for a free speaker rough minutes per section.

   Ask the user once, in one message, only for gaps that change the build, step 2's inputs included; otherwise default to 16:9, a room up to 30 m, Chrome, offline, the deck's language. Done when every fact has a value or a stated default.

2. **Extract** the deck into `source/` ([references/sources.md](references/sources.md) per format).
   - **PPTX:** `<skill>/run python3 -I <skill>/scripts/extract_pptx.py source/deck.pptx source/`. Ask for a PDF export too: only page pictures show the layout, shapes drawn as charts, master and layout text in place, and what `deck.md` marks `[warning]`.
   - **PDF:** it has no speaker notes and leaves out hidden slides: ask for the notes (the PPTX, a notes-pages PDF, or text) and whether hidden slides matter.
   - **Keynote or Google Slides:** ask for a PPTX plus a PDF export. A `.key` file alone yields its pictures and movies, rarely its text.
   - **Slide images:** they are the page pictures; ask for the notes and the originals of logos and photos.

   Look at every page picture: contact sheets first (`<skill>/run python3 -I <skill>/scripts/images.py sheet source/pages/*.png source/sheet.png`), full size wherever a cell is too small to judge, the reading set wherever text is small. Write the inventory into `content.md`, per source slide: its message, every fact, its assets (material under usage rules marked `[licensed: as supplied]`, or `[licensed: approved slide]` when the terms cover the whole slide), its notes. Done when nothing on any slide is missing from `content.md` and every `[warning]` in `deck.md` is resolved or reported.

3. **Verify** every volatile fact (dates, times, rooms, names and titles, numbers, sponsor list and tiers) against the event's official site or program, from its structured data (JSON or API responses, an ICS file) before its rendered page text. Fetch official logos (SVG first) and better photos where the deck's are small. Report each conflict with both versions and the source; the user decides. Done when every volatile fact is marked verified, unverifiable, or reported.

4. **Concept.** Read [references/stagecraft.md](references/stagecraft.md) and [references/choreography.md](references/choreography.md), then write `concept.md`:
   - Visual system: palette and type from the brand (theme.json, logo, website), the one-space device, the tones and the chapters they mark, the energy level (stagecraft.md, Motion budget).
   - Arc: the notes are the script. Place the peak where the one thing from intake lands, and shape the energy around it: a quieter build is the usual shape, an opening hook another. Count the clicks against the slot length.
   - Scene table: `id | message (one sentence) | beat, or quiet | tone | steps | source slides`. Start from messages, not slides: merge, split, reorder, cut. Add a pre-show loop when the screen is on before the talk, and a closing scene when nothing follows on screen.

   For each beat, ask what the content literally is (a count, a share, a sequence, a place, a pair, a person, a promise), let that thing move, and write in the table why this motion is this content. Done when the message column, read top to bottom, tells the audience recorded at intake the talk's argument and peaks on the one thing they should leave with; every inventory item, checked again against the finished table, sits in a scene, in the notes, or on a cut list; every scene has at most one beat, each with its reason; and wherever scenes still map one to one to slides, concept.md says why. Show the user the table and the cut list (must-keep items from intake never on it), the arc, the energy level and the visual system; build after their OK, unless they said to go ahead.

5. **Build.** Copy `<skill>/assets/engine.html` to `show.html`; keep its ENGINE blocks and replace both SHOW blocks and the demo scenes with the concept ([references/engine.md](references/engine.md)). `SHOW.notes` gets the speaker's own notes plus your cues; the speech stays in the speaker's words.
   - Fonts: `<skill>/run python3 -I <skill>/scripts/fonts.py assets/fonts "<Family>:wght@400..800"` for a variable family; a static family takes listed weights (`"Poppins:wght@400;700"`). Brand font files go into `assets/fonts/brand.css` ([references/sources.md](references/sources.md), Brand fonts).
   - Images: `<skill>/run python3 -I <skill>/scripts/images.py logos <logo dir> assets/logos` for sponsor walls, `<skill>/run python3 -I <skill>/scripts/images.py photos <files> assets/photos` for portraits. A QR code: `mkdir -p assets && <skill>/run python3 -I -c 'import segno, sys; segno.make_qr(sys.argv[1]).save(sys.argv[2], light="white")' "<url>" assets/qr-<name>.svg` (black on white, a quiet zone of 4 modules; CSS sets its size). For a logo in its centre, write `make_qr(sys.argv[1], error="h")` and keep the logo within ~20 % of the code's width, on a white pad a module wider all round, clear of the three finder squares and the quiet zone.
   - Particle layer, if concept.md uses one: `mkdir -p assets && cp <skill>/assets/fx.js assets/fx.js`, loaded with `<script src="assets/fx.js"></script>` right before the SHOW script ([references/choreography.md](references/choreography.md)).

   Then `<skill>/run python3 -I <skill>/scripts/build.py build show.html dist/<slug>.html`. Done when the build exits 0, `<html lang>` holds the deck's language and `<title>` the talk's title (hyphenation, screen readers, window titles), the scenes match concept.md's scene table row for row (same ids and order, no demo scene left), `SHOW.notes` holds exactly those ids, and qa.md's font check passes.

6. **QA.** Run every check in [references/qa.md](references/qa.md) against the built file; fix in `show.html`, rebuild, re-run. Done when every check passes on the current build and you have looked at every screenshot.

7. **Handover**, in the deck's language; for a URL instead of a file, host the show first ([references/hosting.md](references/hosting.md)). Done when it holds the dist path (and the URL), the keys (help overlay) and P for the presenter view, stagecraft.md's rehearsal checklist, every QR code with its scene and the address it must open, every volatile fact to reconfirm on the day with where it lives in `show.html` (by scene id or constant name, not line number), each piece of fine print with its size and the rule that requires it, that the file carries the speaker notes, and for material under usage terms what its terms allow (hosting.md); a hosted show serves the built file (hosting.md, Update).

## Changing an existing show

With only a built file, `<skill>/run python3 -I <skill>/scripts/build.py unbundle built.html <dir>` restores `show.html` plus `assets/inline/` and checks that `build` returns the same bytes; on a WARNING instead (another tool's file, an older build.py), diff a rebuild against the original before you edit. `<skill>/run python3 -I <skill>/scripts/build.py strip built.html <out.html>` makes a reading copy.

Engine: compare the version in the show's ENGINE comments with `<skill>/assets/engine.html`. No ENGINE marker: ask the user before you replace its engine. When the skill's is newer, tell the user what changed (engine.md, Versions) and, after their OK, refresh both ENGINE blocks and apply what each newer Versions line says a show must change.

Back up `show.html`, `dist/` and the handover before the first edit. Read feedback about motion against the motion budget. A revised deck: extract it (sources.md, A revised deck), then follow its changes from content.md through concept.md into the scenes and `SHOW.notes` they touch (volatile facts through step 3 again). A new or reworked scene follows step 4 and the contract in engine.md, with its row in concept.md where one exists and its entry in `SHOW.notes`. Done when qa.md's checks for the touched scenes and the navigation walk pass on the rebuilt file (all of qa.md after an engine refresh; after a revised deck, also qa.md's walk at speaking pace over the whole show), the change is in `show.html`, not only in `dist/`, concept.md, `SHOW.notes` and the handover (dist hash, engine version, where things live) match `show.html`, and a hosted show serves the new build (hosting.md, Update).
