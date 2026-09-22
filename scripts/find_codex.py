#!/usr/bin/env python3
"""find_codex.py: print the path of the Codex CLI on this machine.

Works on Windows, macOS and Linux. Looks in this order and stops at the first hit:
  1. `codex` on PATH (npm, Homebrew or the installer put it there)
  2. the usual install folders that a desktop app may not have on its PATH:
       macOS and Linux: /opt/homebrew/bin, /usr/local/bin, ~/.local/bin, ~/.npm-global/bin
       Windows:         %APPDATA%\\npm (codex.cmd)
  3. the OpenAI ChatGPT VS Code extension, newest version wins:
       <home>/<editor>/extensions/openai.chatgpt-<version>-<platform>/bin/<os-cpu>/codex[.exe]
     for .vscode, .vscode-insiders, .vscode-server (Remote SSH and WSL), .vscode-oss
     (VSCodium), .cursor and .windsurf, plus their -server folders. One extension folder
     holds several bin folders (windows-x86_64, linux-x86_64, macos-aarch64, macos-x86_64,
     linux-aarch64), so only the folder for THIS system and CPU counts; a same-system
     folder for another CPU is the fallback.

On Windows an npm install leaves a codex.cmd shim next to a codex file with no extension
that only a POSIX shell can run, so only .exe and .cmd count there, and when the extension
holds a real codex.exe that one wins over a .cmd shim.

Usage:
    python find_codex.py            prints the path, exit 0   (python3 on macOS and Linux)
    python find_codex.py --quiet    prints nothing, exit code only

Exit codes: 0 found, 1 not found.
"""
import argparse
import glob
import os
import platform
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ (embeds local paths) inside the skill folder

EXT_DIRS = [
    ".vscode/extensions",
    ".vscode-insiders/extensions",
    ".vscode-server/extensions",
    ".vscode-server-insiders/extensions",
    ".vscode-oss/extensions",
    ".vscodium-server/extensions",
    ".cursor/extensions",
    ".cursor-server/extensions",
    ".windsurf/extensions",
    ".windsurf-server/extensions",
]

# The extension names its bin folders <os>-<cpu>: os is windows, macos or linux, cpu is
# x86_64 or aarch64. An older or renamed macOS folder may say darwin, so both are accepted.
OS_PREFIXES = {"windows": ("windows",), "macos": ("macos", "darwin"), "linux": ("linux",)}

SHIM_SUFFIXES = (".cmd", ".bat")
WINDOWS_RUNNABLE = (".exe", ".cmd", ".bat", ".com")

INSTALL_HINT = (
    "Install the OpenAI ChatGPT extension in VS Code (marketplace id openai.chatgpt) and sign in "
    "with your ChatGPT account, or install the CLI: npm i -g @openai/codex (macOS also: "
    "brew install --cask codex), then run: codex login. Already have Codex somewhere on this "
    "machine? Pass its full path with --codex."
)


def this_system(system=None, machine=None):
    """(os_tag, arch_tags, binary_name) for the machine running this script.

    `system` and `machine` exist for tests; they default to sys.platform and platform.machine().
    """
    system = (system or sys.platform).lower()
    machine = (platform.machine() if machine is None else machine).lower()
    if system.startswith("win"):
        os_tag, binary = "windows", "codex.exe"
    elif system == "darwin":
        os_tag, binary = "macos", "codex"
    else:
        os_tag, binary = "linux", "codex"
    if machine in ("arm64", "aarch64"):
        arch_tags = ("aarch64", "arm64")
    elif machine in ("x86_64", "amd64", "x64", ""):
        arch_tags = ("x86_64", "x64", "amd64")
    else:
        arch_tags = (machine,)
    return os_tag, arch_tags, binary


def _version_key(path):
    m = re.search(r"openai\.chatgpt-(\d+)\.(\d+)\.(\d+)", str(path))
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _well_known_dirs(home, os_tag):
    if os_tag == "windows":
        appdata = os.environ.get("APPDATA")
        return [Path(appdata) / "npm"] if appdata else []
    return [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), home / ".local" / "bin", home / ".npm-global" / "bin"]


def is_shim(path):
    """True for an npm .cmd or .bat wrapper on Windows (cmd.exe re-parses its arguments)."""
    return Path(path).suffix.lower() in SHIM_SUFFIXES


def bundle_codex(home, os_tag, arch_tags, binary):
    """The newest extension binary for this system and CPU, else for this system, else None."""
    candidates = []
    for ext_dir in EXT_DIRS:
        base = home / ext_dir
        if not base.is_dir():
            continue
        pattern = str(base / "openai.chatgpt-*" / "bin" / "*" / binary)
        candidates.extend(p for p in glob.glob(pattern) if os.path.isfile(p))
    prefixes = OS_PREFIXES[os_tag]
    same_os = [p for p in candidates if Path(p).parent.name.lower().startswith(prefixes)]
    same_cpu = [p for p in same_os if any(tag in Path(p).parent.name.lower() for tag in arch_tags)]
    pool = same_cpu or same_os
    if not pool:
        return None
    pool.sort(key=_version_key, reverse=True)
    return pool[0]


def path_codex(home, os_tag):
    """The codex on PATH or in a well-known install folder, or None. Windows: .exe or .cmd only."""
    names = ["codex.exe", "codex.cmd"] if os_tag == "windows" else ["codex"]
    for name in names:
        hit = shutil.which(name)
        if hit:
            return hit
    for folder in _well_known_dirs(home, os_tag):
        for name in names:
            p = folder / name
            if p.is_file():
                return str(p)
    return None


def find_codex(home=None, system=None, machine=None, use_path=True):
    """Return the path of the Codex binary for this system, or None.

    `home`, `system`, `machine` and `use_path=False` exist for tests that build a fake
    home folder; real callers pass nothing.
    """
    home = Path(home) if home else Path.home()
    os_tag, arch_tags, binary = this_system(system, machine)
    shim = None
    if use_path:
        hit = path_codex(home, os_tag)
        if hit and not (os_tag == "windows" and is_shim(hit)):
            return hit
        shim = hit  # a .cmd shim runs, but the extension's codex.exe is better when it exists
    return bundle_codex(home, os_tag, arch_tags, binary) or shim


def executable_problem(path, system=None):
    """None when the binary can run, else a one-line fix."""
    system = (system or sys.platform).lower()
    if system.startswith("win"):
        if Path(path).suffix.lower() in WINDOWS_RUNNABLE:
            return None
        return (f"{path} is not a Windows executable (no .exe or .cmd extension). Point --codex at "
                "codex.exe inside the ChatGPT extension folder, or at codex.cmd from npm.")
    if os.access(path, os.X_OK):
        return None
    return f'{path} is not executable. Fix: chmod +x "{path}"'


def main():
    ap = argparse.ArgumentParser(description="Locate the Codex CLI binary.")
    ap.add_argument("--quiet", action="store_true", help="exit code only, no output")
    args = ap.parse_args()
    path = find_codex()
    if not path:
        if not args.quiet:
            os_tag, _, _ = this_system()
            print(f"NOT FOUND: no codex on PATH, none in the usual install folders, and no codex binary "
                  f"for this system ({os_tag}-{platform.machine().lower() or 'unknown'}) in an OpenAI "
                  "ChatGPT extension folder under ~/.vscode/extensions (or the Insiders, Server, "
                  "VSCodium, Cursor and Windsurf folders). " + INSTALL_HINT, file=sys.stderr)
        return 1
    if not args.quiet:
        print(path)
        problem = executable_problem(path)
        if problem:
            print(f"WARN: {problem}", file=sys.stderr)
        elif is_shim(path):
            print(f"WARN: {path} is an npm .cmd shim; briefs are flattened to one line through it. "
                  "The ChatGPT extension's codex.exe is preferred when installed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
