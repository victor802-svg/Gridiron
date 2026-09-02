"""What this build is, and whether it is the current one.

THE PROBLEM THIS EXISTS FOR, observed 2026-09-01: the operator's desktop
bundle was built on 2026-08-29 and had been showing a three-day-old interface
over a live, current record. Nothing was wrong with either half. The record
kept filling, the window kept opening, and the screen simply predated college
football, the desk layout and the rail. A stale build is the most convincing
kind of wrong: everything works, and what you are looking at is a photograph.

So the bundle carries the commit it was built from, says so in the footer in
words, and compares itself against the repository sitting on the same machine.
A build that has fallen behind says how far, and says to rebuild.

OUTSIDE THE PREDICTION CLOSURE, and it has to be: this module shells out to
git and reads a file from the bundle, neither of which belongs anywhere near
the path that writes a probability.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

#: The file a build writes into itself. Absent when running from source, which
#: is not an error -- it is the ordinary case for everyone working on the code.
STAMP_NAME = "build_stamp.json"

#: How long git is given before we give up and say nothing. A launcher that
#: hangs because a repository is in a strange state is worse than a launcher
#: that cannot tell you how old it is.
GIT_TIMEOUT = 5.0


def stamp_path(root: Path | None = None) -> Path:
    from . import config
    return (root or config.PACKAGE_ROOT) / STAMP_NAME


def stamp(root: Path | None = None) -> dict | None:
    """{'commit': ..., 'built_utc': ...} for a build, None from source."""
    path = stamp_path(root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if not data.get("commit"):
        return None
    return data


def build_id(root: Path | None = None) -> str:
    """A short, stable name for the build that is running (GRIDIRON_13 P6).

    THE LAUNCHER COMPARES THIS ACROSS A SOCKET, so it has to mean the same
    thing on both sides and survive being carried in JSON. A frozen build
    answers with its stamped commit; running from source answers with the
    working tree's HEAD, and "source" when there is not even that.

    IT IS NOT A SECRET AND IT IS NOT DATA. `/api/health` is the one route that
    answers before authentication, and it carries no counts, no staleness and
    no paths for exactly that reason. A build identifier is the same class of
    thing as the version string already there: it says which code is running,
    which is what the caller has to know in order to notice it is the wrong
    code.
    """
    stamped = stamp(root)
    if stamped and stamped.get("commit"):
        return str(stamped["commit"])[:12]
    head = repository_head()
    return str(head)[:12] if head else "source"


def _git(repo: Path, *args: str) -> str | None:
    """One git command, or None. Never raises -- see GIT_TIMEOUT."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def repository_head(repo: Path | None = None) -> str | None:
    """What the repository on this machine is currently at."""
    from . import config
    return _git(Path(repo or config.PACKAGE_ROOT.parent), "rev-parse", "HEAD")


def commits_behind(built_from: str, head: str, repo: Path | None = None) -> int | None:
    """How many commits the build is missing. None when it cannot be told.

    None rather than 0 for the unknowable case, and the distinction matters: 0
    means "checked, and it is current", None means "could not check". Reported
    as 0 they would look the same, and the one that is actually a gap in the
    check would look like a clean bill of health.
    """
    from . import config
    if built_from == head:
        return 0
    repo = Path(repo or config.PACKAGE_ROOT.parent)
    count = _git(repo, "rev-list", "--count", f"{built_from}..{head}")
    if count is None:
        return None
    try:
        return int(count)
    except ValueError:
        return None


#: How long an answer is reused. Two `git` calls on every meta payload would
#: put a subprocess launch in front of a page that has to feel instant, and the
#: answer changes about as often as somebody commits. Short enough that a
#: commit made while the window is open shows up within a minute.
FRESHNESS_TTL = 60.0

_CACHED: tuple[float, dict] | None = None


def freshness(root: Path | None = None, repo: Path | None = None,
              use_cache: bool = True) -> dict:
    """Everything the footer and the launcher need, counted once.

    ONE IMPLEMENTATION for both, because the launcher's notice and the
    footer's line making different claims about the same build is precisely
    the confusion this module was written to end.
    """
    global _CACHED
    import time as _time
    if use_cache and _CACHED is not None and _time.monotonic() - _CACHED[0] < FRESHNESS_TTL:
        return _CACHED[1]
    answer = _freshness(root, repo)
    if use_cache:
        _CACHED = (_time.monotonic(), answer)
    return answer


def _freshness(root: Path | None, repo: Path | None) -> dict:
    built = stamp(root)
    head = repository_head(repo)
    behind = None
    if built and head:
        behind = commits_behind(built["commit"], head, repo)
    return {
        "from_source": built is None,
        "commit": (built or {}).get("commit"),
        "built_utc": (built or {}).get("built_utc"),
        "head": head,
        "behind": behind,
        "stale": bool(behind),
    }


def write_stamp(target: Path, repo: Path, commit: str | None = None) -> dict:
    """Called by the build. Writes what is being built, from where.

    The commit is read at BUILD time and baked in; reading it at run time
    would just report whatever the repository is at now, which is the question
    rather than the answer.
    """
    commit = commit or _git(repo, "rev-parse", "HEAD") or "unknown"
    data = {
        "commit": commit,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
