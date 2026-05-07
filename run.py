"""One-command bootstrap + run for the AI Transformation Office app.

Usage:
    python run.py             # bootstrap + launch Reflex (localhost:3000)
    python run.py --reset-db  # drop and re-seed data/app.db
    python run.py --no-run    # bootstrap only

What it does:
    1. Creates a `./venv` virtual environment if missing
    2. Installs everything in requirements.txt
    3. Verifies .env has an Anthropic-compatible API key
    4. Seeds data/app.db if it's missing (otherwise applies an additive
       migration so any new tables are created without dropping data)
    5. Runs `reflex init` (idempotent, only acts on first launch)
    6. Starts `reflex run` — frontend on :3000, backend on :8000
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "venv"
DB = ROOT / "data" / "app.db"
ENV_FILE = ROOT / ".env"
REQUIREMENTS = ROOT / "requirements.txt"

IS_WINDOWS = platform.system() == "Windows"
PYTHON_BIN = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
REFLEX_BIN = VENV / ("Scripts/reflex.exe" if IS_WINDOWS else "bin/reflex")


# ----- pretty -----------------------------------------------------------

def _step(msg: str) -> None:
    print(f"\n\033[1;36m== {msg} ==\033[0m")


def _ok(msg: str) -> None:
    print(f"  \033[32m[ok]\033[0m {msg}")


def _warn(msg: str) -> None:
    print(f"  \033[33m[!] {msg}\033[0m")


def _fail(msg: str) -> None:
    print(f"  \033[31m[FAIL] {msg}\033[0m", file=sys.stderr)


# ----- steps ------------------------------------------------------------

def check_python() -> None:
    if sys.version_info < (3, 10):
        _fail(f"Python 3.10+ required (have {sys.version.split()[0]})")
        sys.exit(1)
    _ok(f"Python {sys.version.split()[0]}")


def ensure_venv() -> None:
    _step("Virtual environment")
    if PYTHON_BIN.exists():
        _ok(f"venv exists at {VENV}")
        return
    print(f"  creating venv at {VENV} (this is a one-time step)…")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    _ok("venv created")


def install_deps() -> None:
    _step("Dependencies")
    if not REQUIREMENTS.exists():
        _fail(f"requirements.txt not found at {REQUIREMENTS}")
        sys.exit(1)
    print(f"  installing from {REQUIREMENTS.name}…")
    subprocess.check_call(
        [str(PYTHON_BIN), "-m", "pip", "install", "-q",
         "-r", str(REQUIREMENTS)]
    )
    _ok("dependencies installed")


def check_env() -> None:
    _step("API key (.env)")
    if not ENV_FILE.exists():
        _warn(
            f"{ENV_FILE.name} not found. Create one with one of: "
            "STRANDS_API_KEY=…, ANTHROPIC_API_KEY=…, or CLAUDE_API_KEY=…"
        )
        return
    text = ENV_FILE.read_text(encoding="utf-8", errors="ignore")
    if any(k in text for k in
           ("STRANDS_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_API_KEY")):
        _ok("API key present (chat will work once your account has credits)")
    else:
        _warn(
            "No STRANDS_API_KEY / ANTHROPIC_API_KEY / CLAUDE_API_KEY in .env "
            "— the chat will return a clear error until you add one."
        )


def seed_db(reset: bool) -> None:
    _step("Database")
    if reset and DB.exists():
        DB.unlink()
        _ok("dropped existing app.db")
    if DB.exists():
        # Run migration (additive create_all) so any new tables are created
        # without dropping data.
        subprocess.check_call(
            [str(PYTHON_BIN), "-c",
             "import sys; sys.path.insert(0, '.'); "
             "from data.seed import metadata; from ato_app.db import engine; "
             "metadata.create_all(engine); print('  migration applied')"],
            cwd=ROOT,
        )
        _ok(f"app.db exists at {DB.relative_to(ROOT)}")
        return
    print("  seeding new app.db (1,000 customers · 1,096 daily revenue rows · 5,000 telemetry rows)…")
    subprocess.check_call(
        [str(PYTHON_BIN), "data/seed.py"],
        cwd=ROOT,
    )
    _ok(f"seeded {DB.relative_to(ROOT)}")


def reflex_init() -> None:
    _step("Reflex first-time init")
    if (ROOT / ".web").exists():
        _ok(".web/ exists - skipping init")
        return
    if not REFLEX_BIN.exists():
        _fail(f"reflex CLI missing at {REFLEX_BIN}")
        sys.exit(1)
    subprocess.check_call(
        [str(REFLEX_BIN), "init", "--template", "blank"],
        cwd=ROOT,
    )
    _ok("reflex initialized")


def reflex_run() -> None:
    _step("Starting Reflex dev server")
    print("  Frontend -> http://localhost:3000")
    print("  Backend  -> http://localhost:8000")
    print("  Press Ctrl+C to stop.\n")
    os.execv(str(REFLEX_BIN), [str(REFLEX_BIN), "run"])  # replaces this process


# ----- main -------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--reset-db", action="store_true",
                   help="Drop and re-seed data/app.db")
    p.add_argument("--no-run", action="store_true",
                   help="Bootstrap everything but don't start the server")
    args = p.parse_args()

    print("\033[1mAI Transformation Office - bootstrap\033[0m")
    check_python()
    ensure_venv()
    install_deps()
    check_env()
    seed_db(reset=args.reset_db)
    reflex_init()

    if args.no_run:
        _ok("Bootstrap complete. Run `python run.py` to start the app.")
        return
    reflex_run()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        _fail(f"command failed (exit {e.returncode})")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
