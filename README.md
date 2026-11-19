# stage-show

An [Agent Skill](https://agentskills.io) that turns a slide deck (.pptx, PDF, Keynote, slide images) into a **stage show**: an animated presentation in one offline HTML file that the speaker clicks through on the big screen. The agent treats the deck as raw material, checks volatile facts, and proposes a concept (one message per scene, the arc of the talk, the few moments that move); after your OK it builds the show (clicker navigation, presenter view with notes and timer, reduced motion) and checks it in a scripted browser.

Ask, for example: "Turn talk.pptx into a stage show for Friday's opening."

## Requirements

- a POSIX shell: Linux or macOS (Windows via WSL)
- [mise](https://mise.jdx.dev) 2026.8.14 or newer. It installs Python, poppler and tesseract with every language, and a venv under `~/.cache/stage-show` with Pillow, segno and zxing-cpp (QR codes) and Playwright, whose Chromium goes to `~/.cache/ms-playwright` (`~/Library/Caches/ms-playwright` on macOS). About 2.5 GB in all: Chromium 0.7 GB, tesseract 0.5 GB, poppler 0.25 GB, mise's conda package cache 0.25 GB, download caches up to 0.35 GB, venv and Python 0.3 GB
- Linux or WSL without a desktop: Chromium's system libraries. On Debian or Ubuntu, after Install, run once in a terminal in the skill folder: `./run python3 -m playwright install --with-deps chromium` (uses sudo); elsewhere, install them with the package manager
- an agent that can look at images, Chrome or Chromium for the show, and network access while building (Google Fonts, fact checks)

## Install

```sh
git clone https://github.com/PixelJonas/stage-show ~/.agents/skills/stage-show
cd ~/.agents/skills/stage-show && ./install
```

`./install` keeps mise out of the folders above the skill: in a copy inside a project, it doesn't trust that project's config, install its tools or run its scripts.

Claude Code and Cursor read `~/.claude/skills`: clone into `~/.claude/skills/stage-show` instead. Codex, Gemini CLI and Kimi Code read only `~/.agents/skills`: next to one of them, keep the clone there and link it for Claude Code, so the copies can't drift apart: `mkdir -p ~/.claude/skills && ln -s ~/.agents/skills/stage-show ~/.claude/skills/stage-show`. For one project, copy this folder into the project's `.claude/skills/` or `.agents/skills/` and run `./install` in the copy. Other agents: see their documentation. The folder name must stay `stage-show`.

Without mise: python3 3.9 or newer (plus `python3-venv` on Debian and Ubuntu), poppler 21.11 or newer (`poppler-utils` on Debian and Ubuntu, `poppler` on Homebrew), tesseract with your decks' languages (`tesseract-ocr` plus `tesseract-ocr-<lang>` on Debian and Ubuntu, `tesseract` plus `tesseract-lang` on Homebrew). In a venv, run `pip install -r requirements.txt` and `python -m playwright install chromium`, and start the agent with that venv active. The skill's `run` passes every command through to what PATH finds when it finds no mise, or always with `STAGE_SHOW_NO_MISE=1`.

Optional, by hand: LibreOffice renders a .pptx that comes without a PDF export.

## Update

A clone: `git pull && ./install` in the skill folder. A copy: replace it with the new version, then run `./install` in it. `./install` adds new tool versions, brings the venv's packages to the pins in requirements.txt and rebuilds the venv after a Python pin change (every copy on the machine shares this venv). Without mise, run the two venv commands again.

## Licence

MIT, see [LICENSE](LICENSE).
