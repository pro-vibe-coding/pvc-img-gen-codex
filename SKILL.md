---
name: pvc-img-gen-codex
description: Generates and edits real images from a text brief through the OpenAI Codex CLI that comes with the ChatGPT VS Code extension, on the user's ChatGPT account instead of Claude tokens. Use when asked to "generate an image", "make me a picture of X", "create the hero shot", "render the product photo", "make a transparent PNG of the logo", "change only the background of this image", "we need visuals for this page", or any time a page, post, deck, thumbnail or card needs an image that does not exist yet. Also use to edit an existing image while keeping named parts unchanged. Works on Windows, macOS and Linux; not in the web version of Claude Code. Requires the ChatGPT VS Code extension (openai.chatgpt) signed in, or the Codex CLI; Pillow optional. Not for local GPU generation (ComfyUI), not for judging an image already made (pvc-image-check), not for reading video (pvc-claude-vision), not for PVC skill card art (pvc-skill-art).
metadata:
  author: pvc
  version: "0.2.0"
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0 -->

# pvc-img-gen-codex

Claude cannot paint. Codex can. The OpenAI ChatGPT VS Code extension bundles an authenticated Codex CLI that generates and edits images through the user's ChatGPT account, and this skill drives it: one call, one PNG, verified on disk before anyone trusts it. Runs cost ChatGPT quota, not Claude tokens. Runs on Windows, macOS and Linux. Proven on six concurrent portrait renders, background swaps that kept six faces intact, and brand boards that printed hex codes correctly.

## When to Use

- A page, post, deck, thumbnail, card or share image needs a picture that does not exist yet
- The user asks for a picture, image, shot, render, visual, illustration, cutout or mockup in plain words, even without naming Codex
- An existing image is right except for one thing (background, one object, a color) and the fix should keep everything else exactly as it is
- A cutout with a real transparent background is needed for compositing onto a page

## Where It Runs

| Place | Works? |
|-------|--------|
| Claude Code in a terminal, VS Code, Cursor, Windsurf or a JetBrains IDE | Yes, when Codex is signed in on that machine |
| The Claude desktop app, in a local session | Yes, same condition; the finder also checks the Homebrew and npm folders a desktop app may not have on its PATH |
| Windows, macOS, Linux, WSL and Remote SSH (the `.vscode-server` extension folder) | Yes |
| Claude Code on the web (claude.ai/code), a session started as Cloud, or any other cloud sandbox | No. There is no signed-in Codex there. Print Path D in one line and stop; do not try to install one |

Every command below shows `python`. Run `python3 --version` once first: when it answers, use `python3` for every command in this skill (the usual case on macOS and Linux). On Windows use `py` when `python` is not found or opens the Microsoft Store.

## What This Skill Does Not Do

- Local GPU generation: that belongs to a local tool such as ComfyUI, not this skill
- Judging a finished image for six fingers, doubled cutlery or warped text: that is `pvc-image-check`, run it after every render
- Video frames, YouTube or screen recordings: that is `pvc-claude-vision` or `pvc-video-to-transcript`
- Pixel retouching, webp conversion or cropping: do those in PIL after the render, this skill only produces the source PNG
- Style rules: the project's brand-kit.md (or the user) owns palette, light and mood; this skill turns them into a prompt, it does not invent them

## Trigger Examples

Should trigger on:

- "Generate the hero image for the pizza page"
- "Make me a picture of a red apple on a white table"
- "Can you get a transparent PNG of the mascot for the header?"
- "The background on hero.png is wrong, swap it for a night street but keep the people"
- "We need six portraits for the team section"

Should NOT trigger on:

- "Check hero.png for artifacts before we commit" (pvc-image-check)
- "Render this on my own GPU with ComfyUI" (local generator, not this skill)
- "What happens at 2:10 in this video?" (pvc-claude-vision)
- "Make the card art for pvc-cache-bump" (pvc-skill-art, which drives this skill's gen_image.py itself)

## Step 1: Confirm Codex Exists

Run the finder (do not read its source):

```bash
python ".claude/skills/pvc-img-gen-codex/scripts/find_codex.py"
```

It prints the binary path, or `NOT FOUND` with the install hint. On `NOT FOUND` stop and print Path D below; nothing else in this skill works without it. The finder checks PATH first, then the usual install folders (Homebrew and npm global, which a desktop app may not have on its PATH), then the newest `openai.chatgpt-*` extension bundle under the VS Code, Insiders, Server, VSCodium, Cursor and Windsurf folders in the user's home. A bundle holds one `bin` folder per system, so the finder takes only the folder for this system and CPU, and the version bump on every extension update never breaks it. On macOS and Linux it also prints a `WARN` line with a `chmod +x` command when the binary is not executable; run that line, then go on. On Windows it prefers the extension's `codex.exe` over an npm `codex.cmd` shim and prints a `WARN` when only the shim exists (a shim takes one-line briefs only; the runner flattens the brief itself). When the user says Codex works in their terminal but the finder prints `NOT FOUND`, ask for the full path and pass it with `--codex` on every gen_image.py call.

## Step 2: Pick the Mode

Three modes. Pick before running anything; say which one you picked in one line.

| Mode | Use it when | Cost |
|------|-------------|------|
| Make | The image does not exist yet | one Codex run, about 2 minutes |
| Edit | An image exists and only a named part should change | one Codex run, keeps the approved parts |
| Batch | Several independent images are needed (a team row, a set of cards) | one run each, all in parallel, still about 2 minutes wall time |

Default to Make. Pick Edit over a fresh Make whenever the owner has already approved part of the image: an edit keeps the approved pixels, a regen re-rolls the whole image. Cap edits at two on one image; after that fold every learned constraint into one fresh Make prompt, because each edit re-renders the whole frame and softness compounds like re-saving a JPEG. If the user says "just regenerate" or "start over", skip Edit and Make fresh.

## Step 3: Write the Brief

The script wraps the brief with the save instruction. Write only the scene. A brief that works has, in this order:

1. Subject and action, concrete nouns ("a wood-fired margherita pizza on a dark slate board")
2. Setting and light ("on a rustic oak table, warm side light from a window on the left")
3. Framing ("close three-quarter view, the board fills the lower two thirds")
4. Style words from the brand kit ("editorial food photography, shallow depth of field")
5. Exclusions, one line ("no text, no hands, no cutlery")

Rules the renders taught:

- Remove object classes the model miscounts instead of constraining counts: "no cutlery" works, "exactly two forks" does not. Keep objects the scene requires (chairs at a set table) and constrain them simply
- Text in the image: keep it to a few short strings and check the spelling on arrival; named labels are safer than hex codes when a hex misrenders
- Blending into a page: bake the page's exact background hex into the scene ("the scene fades into flat #0F1115 at the edges") and edge-fade in PIL afterwards; never fake the blend with CSS masks
- Transparent cutout: say "isolated on a fully TRANSPARENT background, PNG with alpha" and run with `--transparent` so the alpha gets verified (a fully transparent pixel must exist; the four corner alphas are reported, and a subject that reaches a corner gets a note, not a fail); a painted white or checkerboard background fails that check on purpose
- Edit prompts state invariants first, then the single change: "Keep the six people, their faces, poses and clothes exactly as they are. Replace only the background with ..."

When a project keeps a prompt log (client kits do, in prompts.md), write the exact prompt, the date and a one-line reason there BEFORE running.

## Step 4: Run

One image per call. Output names are lowercase, hyphenated, `.png`, a bare file name (the folder goes in `--cwd`; the script refuses a folder inside `--out`), and never overwrite the edit source.

Every render takes about 2 minutes, longer than Claude Code's default Bash timeout. Launch every gen_image.py call with Bash `run_in_background` and collect its status line when it finishes, the way Batch does. A foreground call needs a 10 minute timeout (600000 ms, the out-of-the-box ceiling) on the Bash call and `--retries 0`, so the script's two default attempts cannot outrun it. When a foreground call still hits its timeout, Claude Code moves it to the background and reports the task and its output file; collect the status line from there, the quota is not lost.

Make:

```bash
python ".claude/skills/pvc-img-gen-codex/scripts/gen_image.py" --cwd "assets/img" --out hero.png "<brief>"
```

Edit:

```bash
python ".claude/skills/pvc-img-gen-codex/scripts/gen_image.py" --cwd "assets/img" --out hero-v2.png --edit hero.png "<invariants, then the one change>"
```

Transparent cutout:

```bash
python ".claude/skills/pvc-img-gen-codex/scripts/gen_image.py" --cwd "assets/img" --out mascot.png --transparent "<brief ending in: isolated on a fully TRANSPARENT background, PNG with alpha>"
```

Batch: launch one call per image in the background (Bash `run_in_background`), each with its own `--out`, then collect the status lines as they finish. Six at once has worked, about 2 minutes each. Above that is untested, so add renders in batches of six.

A brief with quotes, `$`, `%` or line breaks in it, or a long one: save it to a file and pass `--prompt-file brief.txt`, which keeps the brief out of the calling shell's quoting. That path resolves from where you run the command, not from `--cwd`, so give it relative to the repo root or absolute.

Linux boxes and containers: when a FAIL ends with a `Likely cause:` line saying Codex could not start its sandbox, re-run the same command once with `--sandbox danger-full-access`. The script names that cause itself and skips its own retry. Codex may then write anywhere, so keep `--cwd` on the image folder.

The script finds Codex, builds the command with the prompt BEFORE `-i` (the flag is greedy and eats a trailing prompt as a file path), runs it with a 10 minute timeout, retries once when no new file appears, and verifies the PNG opens. A file only counts when it was written during the run, so a leftover from an earlier render never passes as new. With Pillow present it also reports width, height and mode, and on `--transparent` checks that a fully transparent pixel exists and reports the four corner alphas.

## Step 5: Look, Then Hand Off

1. Read the PNG (the Read tool shows it). Confirm the subject, the framing and the exclusions in one sentence
2. Run `pvc-image-check` on it when that skill is installed in the project. When it is not, say so and do the object-logic look yourself: count hands and fingers, count cutlery and chair legs, read any lettering, trace shadows and crop edges
3. Post-processing (webp, resize, edge-fade) comes after the check, never before. Never upscale a render that came back under target; output at the native size

## What To Print

One of six shapes, always ending with the next action.

Path A, OK (the happy path):

```
Mode: Make
Prompt logged: docs/prompts.md (2026-08-29)
OK: assets/img/hero.png 1536x1024 RGB 2.1 MB (158s)
Seen: slate board with one margherita, oak table, warm left light, no text, no hands.
Next: running pvc-image-check on hero.png.
```

Path B, FAIL (Codex ran but no usable file, after the built-in retry):

```
Mode: Make
FAIL: no usable hero.png after 2 attempts.
Codex tail: <last lines from the script>
Likely cause: the brief asked for a saved file name with a folder in it; Codex writes only into the working directory.
Next: fixed brief below, one more run on your go.
```

Path C, TRANSPARENCY FAIL (file exists, alpha is fake):

```
Mode: Make (transparent)
FAIL (transparency): assets/img/mascot.png 1024x1024 RGB, NO alpha channel (background is painted). Not retrying: rewrite the brief.
Next: brief rewritten to "isolated on a fully TRANSPARENT background, PNG with alpha, no backdrop, no floor, no shadow plate"; run it on your go.
```

Path D, NO-CODEX (nothing to run):

```
NO-CODEX: no codex on PATH, in the usual install folders, or in an editor extension folder under your home.
Install the OpenAI ChatGPT extension in VS Code (marketplace id openai.chatgpt), sign in with your ChatGPT account, then ask again; the finder reads the extension folder on every run. Or install the CLI (npm i -g @openai/codex, or brew install --cask codex on a Mac), run codex login, and restart Claude Code so its shell sees the new PATH.
Alternative: any local image generator you already run (for example ComfyUI).
Already have Codex somewhere on this machine? Give me its full path and I will re-run with --codex <path>.
```

Path E, QUOTA (Codex refused on auth or usage limit):

```
QUOTA: Codex refused after 4s (usage limit reached).
Brief kept below, unchanged. Re-run when the ChatGPT limit resets, or sign in again if the message said not authenticated.
```

Path F, BATCH (several images in one run): one status line per file in launch order, then one Next line.

```
Mode: Batch (3 runs in parallel)
OK: team-01.png 1024x1536 RGB (164s)
FAIL: team-04.png, no usable file after 2 attempts (Codex tail below)
OK: team-05.png 1024x1536 RGB (172s)
Next: pvc-image-check on the two, then one more run for team-04.png with the tightened brief.
```

## Worked Examples

### Make, happy path

User: "Make me a picture of a red apple on a white table."

Run:

```bash
python ".claude/skills/pvc-img-gen-codex/scripts/gen_image.py" --cwd tests --out test-apple.png --retries 0 "A single red apple on a plain white wooden table, soft daylight from the left, photographic, no text"
```

Script output (real run, 2026-08-29, paths shortened):

```
codex: ~/.vscode/extensions/openai.chatgpt-26.707.41301-win32-x64/bin/windows-x86_64/codex.exe
mode: generate
target: tests/test-apple.png
attempt 1/1 running (about 2 minutes) ...
OK: tests/test-apple.png 1402x1122 RGB 1756545 bytes (159s, codex rc=0)
```

On a Mac the `codex:` line points at `bin/macos-aarch64/codex` (or `bin/macos-x86_64/codex` on Intel), on Linux at `bin/linux-x86_64/codex`; the rest reads the same.

Print:

```
Mode: Make
OK: tests/test-apple.png 1402x1122 RGB 1.7 MB (159s)
Seen: one red apple with stem, centered on white painted planks, soft left light, no text.
Next: pvc-image-check is not installed here; my own look finds one apple, one stem, one shadow, nothing doubled.
```

### Edit, keep everything but one thing

User: "Same apple but green."

Run:

```bash
python ".claude/skills/pvc-img-gen-codex/scripts/gen_image.py" --cwd tests --out test-apple-green.png --edit test-apple.png "Keep the apple, the table, the lighting and the framing exactly as they are. Change only the apple's color from red to green."
```

Print:

```
Mode: Edit (1 of 2 allowed on this image)
OK: tests/test-apple-green.png 1402x1122 RGB 1.7 MB (100s)
Seen: same framing and planks, apple now green, stem and shadow unchanged.
Next: pvc-image-check on test-apple-green.png, comparing against test-apple.png for drift.
```

### Batch, six portraits

User: "We need six team portraits for the about page."

Launch six background calls, one per person, same style block, different `--out` (`team-01.png`, `team-02.png`, ...). Collect the six status lines, then print one block:

```
Mode: Batch (6 runs in parallel)
OK: team-01.png 1024x1536 RGB (164s)
OK: team-02.png 1024x1536 RGB (170s)
OK: team-03.png 1024x1536 RGB (166s)
FAIL: team-04.png, no usable file after 2 attempts (Codex tail below)
OK: team-05.png 1024x1536 RGB (172s)
OK: team-06.png 1024x1536 RGB (168s)
Next: pvc-image-check on the five, then one more run for team-04.png with the tightened brief.
```

## Output Rubric

- one_file_per_call: every run names one `--out`, and the print names the file that exists on disk with its size
- verified_not_assumed: the OK line comes from the script's verify step, never from Codex saying it saved something
- mode_stated: the print opens with Make, Edit or Batch, and edits count toward the two-edit cap
- brief_quality: subject, setting, framing, style, exclusions, in that order, with miscounted object classes removed rather than counted
- invariants_first: every edit prompt states what stays before what changes
- hand_off: every OK ends with the pvc-image-check run, or says why it did not and gives the manual look
- voice: no em dashes, PVC voice throughout
- edge_case_coverage: Codex missing (Path D, install hint, local alternative named), web version of Claude Code (Path D, no install attempted), binary not runnable (NO-CODEX with the fix, apply it, retry), npm `.cmd` shim on Windows (brief flattened, extension `codex.exe` preferred), a folder inside `--out` (usage error, put it in `--cwd`), sandbox cannot start on Linux (FAIL names it, one rerun with `--sandbox danger-full-access`), auth or usage limit (Path E, brief kept), no file after retry (Path B, likely cause and fixed brief), fake transparency (Path C, no retry, rewritten brief), edit source equals output name (script refuses, pick a new name), third edit on one image (fold constraints into a fresh Make), long brief (prompt file), pvc-image-check absent (manual object-logic look)

## Resilience

- Codex missing: Path D, stop. Never try to install it or run npm without the user asking
- Binary found but not runnable (macOS, Linux: no exec bit; Windows: a path without `.exe`, `.cmd`, `.bat` or `.com`): the script prints NO-CODEX with the fix and exits 3 before any run. Apply it, then retry
- npm `codex.cmd` shim on Windows: the run works, the brief is flattened to one line and a note says so; the extension's `codex.exe` is preferred when both exist
- Sandbox cannot start (Linux, container, WSL): the FAIL print names it. Re-run once with `--sandbox danger-full-access`, `--cwd` still on the image folder
- Codex refuses on auth or limit: Path E, keep the brief verbatim, stop; the user decides when to retry
- File missing after the script's own retry: Path B with the Codex tail; rewrite the brief once, then wait for a go before spending more quota
- Painted background on a transparent request: Path C, no retry with the same brief
- Timeout (10 minutes): treat as Path B; ChatGPT is slow or queued, say so and offer one retry later
- Edit source not found or same as output: the script exits with a usage error; fix the path or the name, no Codex run happened
- Re-run on a name that already exists: the script says so up front and only reports OK when the file changed during the run. Use `-v2` names when the owner approved the earlier version
- Pillow missing: the script still reports OK on a non-empty file, says size and alpha were not verified; open the file with Read to confirm it decodes

## Installation

Place this folder at `<repo>/.claude/skills/pvc-img-gen-codex/`. Every command in this skill is written relative to the project root, so a project install keeps them working as printed. Claude Code watches `.claude/skills/` and picks the new skill up in the running session. Restart it (reload the VS Code window, or quit and relaunch `claude` in a terminal) only when you just created `.claude/skills/` for the first time, so a session starts watching that folder. Verify by typing `/` in the prompt box and confirming `/pvc-img-gen-codex` is in the list. Then run the finder once to confirm Codex is reachable. Optional self-check that spends no quota: `python ".claude/skills/pvc-img-gen-codex/scripts/test_skill.py"` runs the offline checks (the finder on fake Windows, Mac and Linux folders, the shim rule, the command shape, the PNG verifier) and ends with `N/N checks passed`.
