"""Dev launcher — start backend and frontend together with one command.

Usage:
    uv run python -m scripts.dev

Mirrors ``make dev`` but doesn't require GNU make on PATH. Streams interleaved
logs with prefixed, color-coded lines and propagates Ctrl-C to both children.

Pure stdlib — no new dependencies.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"

BLUE = "\033[34m"
MAGENTA = "\033[35m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def _find(name: str, winget_glob: str | None = None) -> str:
    """Locate an executable by name, falling back to a winget package directory.

    The fallback exists because ``winget install`` updates the user PATH but
    existing shells inherit the old PATH; running this from such a shell would
    otherwise fail with ENOENT even when the binary is on disk.
    """
    found = shutil.which(name)
    if found:
        return found
    if winget_glob:
        winget_root = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        if winget_root.exists():
            for match in winget_root.rglob(winget_glob):
                return str(match)
    raise SystemExit(
        f"{YELLOW}[dev]{RESET} {name!r} not found on PATH. "
        f"Open a fresh terminal so winget's PATH update takes effect, or install {name}."
    )


def _stream(stream: IO[bytes], prefix: str, color: str) -> None:
    """Read lines from a child process and forward to stdout with a colored prefix."""
    for raw in iter(stream.readline, b""):
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        sys.stdout.write(f"{color}[{prefix}]{RESET} {line}\n")
        sys.stdout.flush()


def _terminate(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        sys.stdout.write(f"{YELLOW}[dev]{RESET} {name} did not stop in 5s; killing.\n")
        proc.kill()
        proc.wait()


def main() -> int:
    # Vite emits non-ASCII glyphs (e.g. '➜'); on a Windows cp1252 console the
    # default encoding can't represent those, raising UnicodeEncodeError mid-stream.
    # ``replace`` swaps unencodable chars for '?' rather than killing the streamer.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    uv = _find("uv", winget_glob="uv.exe")
    pnpm = _find("pnpm", winget_glob="pnpm.exe")

    backend_cmd = [uv, "run", "uvicorn", "app.main:app", "--reload", "--port", "8000"]
    frontend_cmd = [pnpm, "--dir", str(FRONTEND_DIR), "dev"]

    sys.stdout.write(
        f"{YELLOW}[dev]{RESET} backend on :8000, frontend on :5173 — Ctrl-C stops both\n"
    )
    sys.stdout.flush()

    backend = subprocess.Popen(
        backend_cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    frontend = subprocess.Popen(
        frontend_cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    streamers = [
        threading.Thread(target=_stream, args=(backend.stdout, "backend", BLUE), daemon=True),
        threading.Thread(target=_stream, args=(frontend.stdout, "frontend", MAGENTA), daemon=True),
    ]
    for t in streamers:
        t.start()

    rc = 0
    try:
        while True:
            b_rc = backend.poll()
            f_rc = frontend.poll()
            if b_rc is not None:
                sys.stdout.write(f"{YELLOW}[dev]{RESET} backend exited (rc={b_rc}); stopping.\n")
                rc = b_rc or 1
                break
            if f_rc is not None:
                sys.stdout.write(f"{YELLOW}[dev]{RESET} frontend exited (rc={f_rc}); stopping.\n")
                rc = f_rc or 1
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        sys.stdout.write(f"\n{YELLOW}[dev]{RESET} Ctrl-C — stopping both…\n")
    finally:
        _terminate(frontend, "frontend")
        _terminate(backend, "backend")
        # Streamer threads are daemons; they'll exit when their pipes close.

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
