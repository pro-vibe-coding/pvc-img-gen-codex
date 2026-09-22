#!/usr/bin/env python3
"""gen_image.py: make or edit ONE image with the Codex CLI, then verify the file.

Works on Windows, macOS and Linux (use `python3` where `python` is Python 2 or missing).

Generation:
    python gen_image.py --cwd assets/img --out hero.png "A wide shot of a wooden table at golden hour, ..."

Edit (keeps what the prompt names as invariant, changes only what it names to fix):
    python gen_image.py --cwd assets/img --out hero-v2.png --edit hero.png "Keep the six people exactly as they are; replace only the background with ..."

Options:
    --out NAME.png       bare file name Codex must write inside --cwd (required; no folder in it)
    --cwd DIR            working directory for the run (default: current directory)
    --edit FILE          edit this existing image instead of generating from scratch (relative to --cwd)
    --prompt-file FILE   read the prompt from a file (path relative to where you run the command)
    --transparent        after the run, verify the PNG has real transparency (a fully transparent
                         pixel exists); the four corner alphas are reported
    --timeout SECONDS    per attempt (default 600)
    --retries N          extra attempts when no fresh file appears (default 1)
    --codex PATH         skip auto-detection and use this binary
    --sandbox MODE       Codex sandbox: workspace-write (default) or danger-full-access, for a
                         Linux box or container where Codex cannot start its own sandbox

A file only counts when it was written during this run: a leftover from an earlier run
never passes as a new render. Prints one status line last: OK, FAIL, QUOTA, or NO-CODEX.
Exit codes: 0 ok, 1 fail, 2 usage, 3 codex missing or not runnable, 4 quota or auth.
Runs cost ChatGPT quota, not Claude tokens.
"""
import argparse
import errno
import re
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ (embeds local paths) inside the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_codex import INSTALL_HINT, executable_problem, find_codex, is_shim  # noqa: E402

QUOTA_RE = re.compile(
    r"usage limit|quota|rate.?limit|too many requests|\b(?:http|status|error)\s*429\b|"
    r"not logged in|not authenticated|login required|unauthori[sz]ed",
    re.I,
)
SANDBOX_RE = re.compile(
    r"bwrap:|bubblewrap|codex-linux-sandbox executable not found|landlock|seccomp|"
    r"sandbox.{0,40}(?:not supported|unavailable|unsupported|failed)",
    re.I,
)

SANDBOX_MODES = ("workspace-write", "danger-full-access")


def exec_flags(sandbox="workspace-write"):
    # Codex CLI 0.154 removed --full-auto. These flags give the same workspace-write
    # sandbox on old and new versions, and let the run work outside a git repo.
    return ["--sandbox", sandbox, "--skip-git-repo-check"]


def build_cmd(codex, prompt, out_name, edit, sandbox="workspace-write"):
    flags = exec_flags(sandbox)
    if edit:
        full = (f"{prompt.strip()} Save the edited image as {out_name} in the current "
                f"working directory. Do not overwrite the input file.")
        # The prompt MUST come before -i: the flag is greedy and swallows a trailing
        # prompt as a file path, then the run dies on "no prompt provided".
        return [codex, "exec", *flags, full, "-i", edit]
    full = f"Generate one image saved as {out_name} in the current working directory: {prompt.strip()}"
    return [codex, "exec", *flags, full]


def run_once(cmd, cwd, timeout):
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except PermissionError as e:
        fix = "" if sys.platform.startswith("win") else f'. Fix: chmod +x "{cmd[0]}"'
        return 126, f"cannot execute {cmd[0]}: {e}{fix}"
    except OSError as e:
        extra = ""
        if getattr(e, "errno", None) == errno.ENOEXEC:
            extra = f". This Codex binary is built for another CPU. {INSTALL_HINT}"
        return 126, f"cannot execute {cmd[0]}: {e}{extra}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def stamp(path):
    """(mtime_ns, size) of the file, or None when it does not exist."""
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def verify(path, transparent):
    if not path.is_file() or path.stat().st_size == 0:
        return False, "file missing or empty"
    try:
        from PIL import Image
    except ImportError:
        return True, f"{path.stat().st_size} bytes (Pillow not installed, dimensions and alpha not verified)"
    try:
        with Image.open(path) as im:
            im.load()
            w, h = im.size
            mode = im.mode
            note = f"{w}x{h} {mode} {path.stat().st_size} bytes"
            if transparent:
                if mode in ("P", "LA", "RGBa"):
                    im = im.convert("RGBA")  # palette and premultiplied files carry real alpha too
                if "A" not in im.mode:
                    return False, note + ", NO alpha channel (background is painted)"
                lowest = im.getchannel("A").getextrema()[0]
                corners = [im.getpixel((0, 0))[-1], im.getpixel((w - 1, 0))[-1],
                           im.getpixel((0, h - 1))[-1], im.getpixel((w - 1, h - 1))[-1]]
                if lowest != 0:
                    return False, note + f", no fully transparent pixel, corner alpha {corners} (fake transparency, background is painted)"
                if max(corners) != 0:
                    note += f", alpha real (corner alpha {corners}: the subject reaches a corner, check the crop)"
                else:
                    note += ", alpha real (all four corners 0)"
            return True, note
    except Exception as e:  # corrupt or partial write
        return False, f"cannot decode: {e}"


def tail_of(log, n):
    return "\n".join(log.strip().splitlines()[-n:])


def likely_cause(log, sandbox):
    """One line naming the usual reason a run wrote nothing, or an empty string."""
    tail = tail_of(log, 40)
    if SANDBOX_RE.search(tail) and sandbox == "workspace-write":
        return ("Likely cause: Codex could not start its sandbox on this system. Re-run with "
                "--sandbox danger-full-access (Codex may then write anywhere, so keep --cwd on the image folder).")
    return ""


def main():
    for stream in (sys.stdout, sys.stderr):  # Codex output can carry box-drawing glyphs
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="Make or edit one image with the Codex CLI.")
    ap.add_argument("prompt", nargs="?", help="the image brief (or use --prompt-file)")
    ap.add_argument("--out", required=True, help="output file name, e.g. hero.png")
    ap.add_argument("--cwd", default=".", help="working directory for the run")
    ap.add_argument("--edit", help="existing image to edit")
    ap.add_argument("--prompt-file", help="read the prompt from this file")
    ap.add_argument("--transparent", action="store_true", help="verify real transparency")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--codex", help="path to the codex binary")
    ap.add_argument("--sandbox", choices=SANDBOX_MODES, default="workspace-write",
                    help="Codex sandbox mode (default workspace-write)")
    args = ap.parse_args()

    if args.prompt_file:
        pf = Path(args.prompt_file)
        if not pf.is_file():
            print(f"usage error: --prompt-file not found: {pf}", file=sys.stderr)
            return 2
        prompt = pf.read_text(encoding="utf-8-sig")
    elif args.prompt:
        prompt = args.prompt
    else:
        print("usage error: give a prompt or --prompt-file", file=sys.stderr)
        return 2
    if not prompt.strip():
        print("usage error: prompt is empty", file=sys.stderr)
        return 2

    cwd = Path(args.cwd).resolve()
    if not cwd.is_dir():
        print(f"usage error: --cwd {cwd} is not a directory", file=sys.stderr)
        return 2
    if Path(args.out).parent != Path("."):
        print("usage error: --out takes a bare file name; put the folder in --cwd", file=sys.stderr)
        return 2
    out_name = args.out
    if not out_name.lower().endswith(".png"):
        print("usage error: --out must end in .png", file=sys.stderr)
        return 2
    out_path = cwd / out_name

    edit = None
    if args.edit:
        edit_path = Path(args.edit)
        if not edit_path.is_absolute():
            edit_path = cwd / edit_path
        if not edit_path.is_file():
            print(f"usage error: --edit file not found: {edit_path}", file=sys.stderr)
            return 2
        if edit_path.resolve() == out_path.resolve():
            print("usage error: --out must differ from --edit (never overwrite the source)", file=sys.stderr)
            return 2
        edit = str(edit_path.resolve())

    codex = args.codex or find_codex()
    if not codex or not Path(codex).exists():
        print(f"NO-CODEX: codex CLI not found. {INSTALL_HINT}")
        return 3
    problem = executable_problem(codex)
    if problem:
        print(f"NO-CODEX: {problem}")
        return 3
    if sys.platform.startswith("win") and is_shim(codex):
        # cmd.exe re-parses the arguments of a .cmd shim: a line break ends the brief early.
        prompt = " ".join(prompt.split())
        print("note: codex is an npm .cmd shim; brief flattened to one line. Avoid double quotes "
              "and % in the brief, or install the ChatGPT extension so codex.exe is used instead.")

    cmd = build_cmd(codex, prompt, out_name, edit, args.sandbox)
    print(f"codex: {codex}")
    print(f"mode: {'edit of ' + edit if edit else 'generate'}")
    print(f"target: {out_path}")
    before = stamp(out_path)
    if before:
        print(f"note: {out_name} already exists; only a file written during this run counts")

    attempts = 1 + max(0, args.retries)
    log = ""
    for attempt in range(1, attempts + 1):
        t0 = time.time()
        print(f"attempt {attempt}/{attempts} running (about 2 minutes) ...", flush=True)
        rc, log = run_once(cmd, cwd, args.timeout)
        elapsed = int(time.time() - t0)
        if rc == 126:
            print(f"NO-CODEX: {log}")
            return 3
        fresh = stamp(out_path) not in (None, before)
        if not fresh:
            if QUOTA_RE.search(tail_of(log, 40)):
                print(f"QUOTA: codex refused (auth or usage limit) after {elapsed}s. Last lines:\n{tail_of(log, 8)}")
                return 4
            print(f"attempt {attempt} wrote no new file (codex rc={rc}, {elapsed}s)")
            if likely_cause(log, args.sandbox):
                break  # the same command fails the same way; do not spend another attempt
            continue
        ok, note = verify(out_path, args.transparent)
        if ok:
            print(f"OK: {out_path} {note} ({elapsed}s, codex rc={rc})")
            return 0
        if args.transparent and out_path.is_file():
            # A painted background is a prompt problem; the same brief paints again.
            print(f"FAIL (transparency): {out_path} {note}. Not retrying: rewrite the brief.")
            return 1
        print(f"attempt {attempt} produced no usable file: {note} (codex rc={rc}, {elapsed}s)")
    cause = likely_cause(log, args.sandbox)
    print(f"FAIL: no usable {out_name} after {attempts} attempt(s). Codex output tail:\n{tail_of(log, 12)}")
    if cause:
        print(cause)
    return 1


if __name__ == "__main__":
    sys.exit(main())
