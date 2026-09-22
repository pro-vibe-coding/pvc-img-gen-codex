# Requirements: pvc-img-gen-codex

What a fresh machine needs before this skill runs. Tick each box once it is on the machine. Commands work in a terminal on Windows (PowerShell or Git Bash), macOS and Linux. Where a command says `python`: on macOS and Linux use `python3` when `python` is missing or is Python 2; on Windows use `py` when `python` is not found or opens the Microsoft Store.

## Required

- [ ] **Python 3.9+** (runtime for the three scripts in `scripts/`)
  Check `python --version` (or `python3 --version`), install https://python.org/downloads (macOS also: `brew install python`; Linux: your package manager)
- [ ] **Codex CLI, signed in to a ChatGPT account** (binary, does the image generation; every run spends ChatGPT quota, not Claude tokens)
  Easiest route: install the OpenAI ChatGPT extension in VS Code (marketplace id `openai.chatgpt`), sign in once, reload the window. The extension carries the `codex` binary (`codex.exe` on Windows) for your system and the skill finds it on its own, including under WSL and Remote SSH (`~/.vscode-server`), VSCodium, Cursor and Windsurf.
  Alternative: `npm i -g @openai/codex` (macOS also: `brew install --cask codex`), then `codex login` and pick "Sign in with ChatGPT".
  Check `python .claude/skills/pvc-img-gen-codex/scripts/find_codex.py` prints a path and no `WARN` line, then run that printed path with `login status`: it says `Logged in using ChatGPT` when signed in
- [ ] **A ChatGPT plan that includes Codex** (account; Plus, Pro, Business, Edu or Enterprise as of 2026-09; every render spends that plan's usage)
  Check: run the finder above, then one small test render
- [ ] **A machine you sit at** (the Codex sign-in lives on the computer that runs Claude Code)
  Claude Code in a terminal, VS Code, Cursor, JetBrains IDEs and a local session of the Claude desktop app all work. Claude Code on the web (claude.ai/code), a session started as Cloud, and other cloud sandboxes do not: there is no signed-in Codex there

## Optional

- [ ] **Node.js 18+ and npm** (only for the `npm i -g @openai/codex` route; not needed when the VS Code extension or Homebrew supplies the binary)
  Check `node --version`, install https://nodejs.org
- [ ] **Pillow** (Python package, verifies the PNG decodes, reports width and height, checks real transparency)
  Without it the script still confirms a non-empty file exists but cannot verify size or alpha. Check `python -c "import PIL"`, install `pip install pillow` (Ubuntu and Debian: `sudo apt install python3-pil`; Homebrew Python refuses a bare pip install, so use a venv or `pip3 install --break-system-packages pillow`)
- [ ] **pvc-image-check** (sibling skill, the object-logic pass after every render)
  Without it the skill does the six-fingers and doubled-cutlery look by hand. Install it into the same project when you have it

## Bundled

Nothing. The skill is three Python scripts and their docs. Codex, Python and Pillow are installed by you and stay outside the skill folder.

## Platform notes

- **Windows:** the extension keeps the binary under `%USERPROFILE%\.vscode\extensions\openai.chatgpt-<version>-win32-x64\bin\windows-x86_64\codex.exe`. Nothing to make executable. An npm install gives `codex.cmd`, which works, but the finder prefers the extension's `codex.exe` when both exist, since a `.cmd` cannot take a multi-line brief
- **macOS:** the extension keeps the binary under `~/.vscode/extensions/openai.chatgpt-<version>-darwin-arm64/bin/macos-aarch64/codex` (Apple Silicon) or `...-darwin-x64/bin/macos-x86_64/codex` (Intel). If the finder prints a `WARN` with a `chmod +x` line, run that line once
- **Linux, WSL, containers:** the extension keeps the binary under `~/.vscode/extensions/` or `~/.vscode-server/extensions/` with `bin/linux-x86_64/codex` (or `linux-aarch64`). Codex starts its own sandbox on Linux; when a run fails saying the sandbox could not start (Landlock, seccomp or bubblewrap unavailable), re-run `gen_image.py` with `--sandbox danger-full-access`

## Self-check with no quota spent

`python .claude/skills/pvc-img-gen-codex/scripts/test_skill.py` runs the offline checks: the finder against fake Windows, macOS and Linux extension folders, the shim rule on Windows, the command shape (prompt before `-i`, no `--full-auto`), and the PNG verifier when Pillow is present. Expect the last line to read `N/N checks passed` with no `FAIL` line (seven PNG checks are skipped without Pillow, and the count is then seven lower).
