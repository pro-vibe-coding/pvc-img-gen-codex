#!/usr/bin/env python3
"""test_skill.py: offline checks for find_codex.py and gen_image.py. No Codex run, no quota spent.

    python scripts/test_skill.py        (python3 on macOS and Linux)

Builds a fake home folder holding the ChatGPT extension's bin folders for several systems and
checks that the finder picks the binary for the system it is told it runs on, newest version
first, and never a shell shim on Windows. Then checks the command shape (prompt before -i,
no --full-auto) and the PNG verifier when Pillow is installed. The count is the same on every
system; seven PNG checks are skipped without Pillow. Exit 0 when every check passes, 1 otherwise.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_codex as fc  # noqa: E402
import gen_image as gi  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    ok = bool(cond)
    RESULTS.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f" [{detail}]" if detail and not ok else ""))


def fake_home(root, versions, bins, editor=".vscode"):
    """Lay out <root>/<editor>/extensions/openai.chatgpt-<v>-any/bin/<os-cpu>/codex[.exe]."""
    home = Path(root)
    for v in versions:
        for b in bins:
            binary = "codex.exe" if b.startswith("windows") else "codex"
            p = home / editor / "extensions" / f"openai.chatgpt-{v}-any" / "bin" / b / binary
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")
            if binary == "codex":
                os.chmod(p, 0o755)
    return home


def pick(home, system, machine, use_path=False):
    hit = fc.find_codex(home=home, system=system, machine=machine, use_path=use_path)
    return Path(hit) if hit else None


def main():
    with tempfile.TemporaryDirectory() as tmp:
        home = fake_home(tmp, ["26.707.41301", "26.908.40401", "26.1000.1"],
                         ["windows-x86_64", "linux-x86_64", "linux-aarch64", "macos-aarch64", "macos-x86_64"])
        w = pick(home, "win32", "AMD64")
        check("windows picks windows-x86_64/codex.exe",
              w and w.name == "codex.exe" and w.parent.name == "windows-x86_64", str(w))
        check("newest version wins numerically (26.1000 over 26.908)", w and "26.1000.1" in str(w), str(w))
        m = pick(home, "darwin", "arm64")
        check("mac apple silicon picks macos-aarch64/codex", m and m.parent.name == "macos-aarch64" and m.name == "codex", str(m))
        mi = pick(home, "darwin", "x86_64")
        check("mac intel picks macos-x86_64/codex", mi and mi.parent.name == "macos-x86_64", str(mi))
        lx = pick(home, "linux", "x86_64")
        check("linux x86_64 picks linux-x86_64/codex", lx and lx.parent.name == "linux-x86_64", str(lx))
        la = pick(home, "linux", "aarch64")
        check("linux aarch64 picks linux-aarch64/codex", la and la.parent.name == "linux-aarch64", str(la))

    with tempfile.TemporaryDirectory() as tmp:
        home = fake_home(tmp, ["26.908.40401"], ["windows-x86_64", "linux-x86_64"])
        m = pick(home, "darwin", "arm64")
        check("mac with no macos folder finds nothing (never the windows or linux binary)", m is None, str(m))
        la = pick(home, "linux", "aarch64")
        check("linux aarch64 falls back to linux-x86_64 (same system, other cpu)",
              la and la.parent.name == "linux-x86_64", str(la))
        w = pick(home, "win32", "ARM64")
        check("windows arm falls back to windows-x86_64", w and w.parent.name == "windows-x86_64", str(w))

    with tempfile.TemporaryDirectory() as tmp:
        home = fake_home(tmp, ["26.908.40401"], ["darwin-arm64"])
        m = pick(home, "darwin", "arm64")
        check("older macOS folder spelled darwin-arm64 is still found", m and m.parent.name == "darwin-arm64", str(m))

    with tempfile.TemporaryDirectory() as tmp:
        home = fake_home(Path(tmp) / "h1", ["26.908.40401"], ["linux-x86_64"], editor=".vscode-server")
        check("remote or WSL folder under .vscode-server is found", pick(home, "linux", "x86_64") is not None)
        home = fake_home(Path(tmp) / "h2", ["26.908.40401"], ["macos-aarch64"], editor=".cursor")
        check("cursor folder is found", pick(home, "darwin", "arm64") is not None)
        home = fake_home(Path(tmp) / "h3", ["26.908.40401"], ["linux-x86_64"], editor=".cursor-server")
        check("cursor remote folder is found", pick(home, "linux", "x86_64") is not None)
        home = fake_home(Path(tmp) / "h4", ["26.908.40401"], ["macos-aarch64"], editor=".vscode-insiders")
        check("insiders folder is found", pick(home, "darwin", "arm64") is not None)

    with tempfile.TemporaryDirectory() as tmp:
        check("empty home finds nothing", pick(Path(tmp), "linux", "x86_64") is None)

    # PATH handling: a real binary on PATH wins; a Windows .cmd shim loses to the extension's codex.exe
    real_which = fc.shutil.which
    try:
        with tempfile.TemporaryDirectory() as tmp:
            home = fake_home(tmp, ["26.908.40401"], ["windows-x86_64", "linux-x86_64"])
            fc.shutil.which = lambda name: "C:\\fake\\npm\\codex.cmd" if name == "codex.cmd" else None
            w = pick(home, "win32", "AMD64", use_path=True)
            check("windows: extension codex.exe beats the npm .cmd shim", w and w.name == "codex.exe", str(w))
            fc.shutil.which = lambda name: "/usr/local/bin/codex" if name == "codex" else None
            lx = pick(home, "linux", "x86_64", use_path=True)
            check("linux: codex on PATH wins over the extension folder", str(lx).replace("\\", "/") == "/usr/local/bin/codex", str(lx))
        with tempfile.TemporaryDirectory() as tmp:
            fc.shutil.which = lambda name: "C:\\fake\\npm\\codex.cmd" if name == "codex.cmd" else None
            w = pick(Path(tmp), "win32", "AMD64", use_path=True)
            check("windows: the .cmd shim is used when no extension folder exists",
                  w and str(w).replace("\\", "/").endswith("/codex.cmd"), str(w))
    finally:
        fc.shutil.which = real_which
    check("is_shim: codex.cmd is a shim", fc.is_shim("C:\\x\\codex.cmd"))
    check("is_shim: codex.exe is not", not fc.is_shim("C:\\x\\codex.exe"))

    # executable check: two checks on every system so the count stays the same
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "codex"
        p.write_bytes(b"x")
        if os.name == "nt":
            prob = fc.executable_problem(str(p), system="win32")
            check("windows: a bare codex file is refused with the .exe/.cmd hint", prob is not None and ".exe" in prob, str(prob))
            check("windows: codex.exe passes the check", fc.executable_problem("C:\\x\\codex.exe", system="win32") is None)
        else:
            os.chmod(p, 0o644)
            prob = fc.executable_problem(str(p), system="linux")
            check("non-executable binary gets the chmod hint", prob is not None and "chmod +x" in prob, str(prob))
            os.chmod(p, 0o755)
            check("executable binary passes", fc.executable_problem(str(p), system="linux") is None)

    cmd = gi.build_cmd("codex", "a red apple", "apple.png", None)
    check("generate: sandbox flags present",
          "--sandbox" in cmd and "workspace-write" in cmd and "--skip-git-repo-check" in cmd, str(cmd))
    check("generate: no --full-auto (removed in Codex CLI 0.154)", "--full-auto" not in cmd)
    check("generate: prompt names the file", any("apple.png" in c for c in cmd))
    cmd = gi.build_cmd("codex", "keep all, change color", "apple-v2.png", "/x/apple.png", "danger-full-access")
    check("edit: prompt comes before -i", cmd.index("-i") == len(cmd) - 2 and cmd[-1] == "/x/apple.png", str(cmd))
    check("edit: sandbox mode passes through", "danger-full-access" in cmd)

    check("sandbox failure is named with the fix",
          "danger-full-access" in gi.likely_cause("error: Landlock not supported here", "workspace-write"))
    check("bubblewrap failure is named too",
          "danger-full-access" in gi.likely_cause("bwrap: No permissions to create a new namespace", "workspace-write"))
    check("no false sandbox cause on a normal log", gi.likely_cause("saved image", "workspace-write") == "")
    check("quota regex catches usage limit", gi.QUOTA_RE.search("You've hit your usage limit") is not None)
    check("quota regex catches not logged in", gi.QUOTA_RE.search("error: not logged in") is not None)

    try:
        from PIL import Image
    except ImportError:
        Image = None
        print("SKIP: Pillow not installed, seven verify() checks skipped")
    if Image:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            Image.new("RGB", (8, 8), (200, 10, 10)).save(t / "rgb.png")
            ok, note = gi.verify(t / "rgb.png", False)
            check("verify: rgb png passes without --transparent", ok and "8x8 RGB" in note, note)
            ok, note = gi.verify(t / "rgb.png", True)
            check("verify: rgb png fails --transparent", not ok and "NO alpha" in note, note)
            Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(t / "real.png")
            ok, note = gi.verify(t / "real.png", True)
            check("verify: real alpha passes", ok and "alpha real" in note, note)
            im = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
            im.putpixel((4, 4), (0, 0, 0, 0))
            im.save(t / "corner.png")
            ok, note = gi.verify(t / "corner.png", True)
            check("verify: subject reaching a corner still passes with a note", ok and "reaches a corner" in note, note)
            Image.new("RGBA", (8, 8), (255, 255, 255, 255)).save(t / "fake.png")
            ok, note = gi.verify(t / "fake.png", True)
            check("verify: painted RGBA fails as fake transparency", not ok and "fake transparency" in note, note)
            (t / "empty.png").write_bytes(b"")
            ok, note = gi.verify(t / "empty.png", False)
            check("verify: empty file fails", not ok, note)
            (t / "bad.png").write_bytes(b"not a png")
            ok, note = gi.verify(t / "bad.png", False)
            check("verify: corrupt file fails", not ok and "cannot decode" in note, note)

    check("stamp: missing file is None", gi.stamp(Path(tempfile.gettempdir()) / "no-such-file-xyz.png") is None)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
