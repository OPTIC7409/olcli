"""
OLCLI Auto-Updater
Checks for new commits on origin/main at startup, pulls if behind,
reinstalls the package, and restarts the process transparently.
"""

import os
import sys
import subprocess
from pathlib import Path


def _repo_root() -> Path | None:
    """Return the repo root by walking up from this file, or None if not in a git repo."""
    here = Path(__file__).resolve().parent.parent
    if (here / ".git").exists():
        return here
    return None


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def check_and_update(console=None) -> bool:
    """
    Check for upstream changes and update if needed.

    Returns True if an update was applied (caller should expect a restart).
    Returns False if already up to date or update was skipped/failed.

    `console` is an optional Rich Console for pretty output; falls back to print().
    """

    def info(msg: str):
        if console:
            console.print(f"[dim]ℹ {msg}[/dim]")
        else:
            print(f"  {msg}")

    def success(msg: str):
        if console:
            console.print(f"[bold green]✓ {msg}[/bold green]")
        else:
            print(f"✓ {msg}")

    def warn(msg: str):
        if console:
            console.print(f"[bold yellow]⚠ {msg}[/bold yellow]")
        else:
            print(f"⚠ {msg}")

    repo = _repo_root()
    if repo is None:
        # Installed as a non-editable package — can't self-update from git
        return False

    # ── 1. Fetch latest refs (quiet, non-blocking feel) ───────────────────────
    fetch = _run(["git", "fetch", "--quiet", "origin", "main"], cwd=repo)
    if fetch.returncode != 0:
        # No network / not a git remote — silently skip
        return False

    # ── 2. Compare local HEAD with origin/main ────────────────────────────────
    local = _run(["git", "rev-parse", "HEAD"], cwd=repo)
    remote = _run(["git", "rev-parse", "origin/main"], cwd=repo)

    if local.returncode != 0 or remote.returncode != 0:
        return False

    local_sha = local.stdout.strip()
    remote_sha = remote.stdout.strip()

    if local_sha == remote_sha:
        # Already up to date — nothing to do
        return False

    # ── 3. Count commits behind ───────────────────────────────────────────────
    behind = _run(
        ["git", "rev-list", "--count", f"{local_sha}..{remote_sha}"],
        cwd=repo,
    )
    n = behind.stdout.strip() if behind.returncode == 0 else "?"

    info(f"Update available ({n} new commit{'s' if n != '1' else ''}) — updating…")

    # ── 4. Pull ───────────────────────────────────────────────────────────────
    pull = _run(["git", "pull", "--ff-only", "origin", "main"], cwd=repo)
    if pull.returncode != 0:
        warn(
            "Auto-update: git pull failed (local changes?). "
            "Run `git pull && pip install -e .` manually."
        )
        return False

    # ── 5. Reinstall package so new entry-points / deps are picked up ─────────
    pip = _run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=repo,
    )
    if pip.returncode != 0:
        warn("Auto-update: pip install failed. Run `pip install -e .` manually.")
        return False

    success("Updated successfully — restarting…")

    # ── 6. Restart the current process with the same arguments ────────────────
    os.execv(sys.executable, [sys.executable] + sys.argv)

    # execv replaces the process; this line is never reached
    return True  # pragma: no cover
