"""Create the access token, once, and write it to .env.

    python tools/make_token.py            # create if absent
    python tools/make_token.py --rotate   # replace, ending every session

The token is printed EXACTLY ONCE, to your terminal, and never again: it is not
logged, not echoed by the server, and not recoverable from the database. If you
lose it, rotate.
"""

from __future__ import annotations

import argparse
import os
import secrets
import stat
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gridiron import auth, config, db  # noqa: E402


def write_env(token: str) -> None:
    """Write the token to .env, preserving anything else already there."""
    lines: list[str] = []
    if auth.ENV_FILE.exists():
        lines = [
            line
            for line in auth.ENV_FILE.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith(f"{auth.TOKEN_VAR}=")
        ]
    lines.append(f"{auth.TOKEN_VAR}={token}")
    auth.ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Owner-only where the OS honours it. On Windows this is advisory; the file
    # still sits in a user-profile directory, which is the real boundary.
    try:
        os.chmod(auth.ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rotate", action="store_true",
                    help="replace an existing token and end every open session")
    args = ap.parse_args()

    existing = auth.read_token()
    if existing and not args.rotate:
        print(f"A token already exists in {auth.ENV_FILE}.")
        print("It is not printed again. To replace it: --rotate")
        return 0

    token = secrets.token_urlsafe(32)
    write_env(token)

    if args.rotate:
        # Rotating must end existing sessions, or the old token's holders keep
        # their access and the rotation was theatre.
        conn = db.open_db(config.DB_PATH)
        dropped = conn.execute("DELETE FROM sessions").rowcount
        conn.commit()
        print(f"Rotated. {dropped} open session(s) ended.")

    print()
    print("=" * 68)
    print("  ACCESS TOKEN - shown once, never again. Store it now.")
    print("=" * 68)
    print()
    print(f"  {token}")
    print()
    print(f"  written to {auth.ENV_FILE}")
    print("  The desktop launcher reads it from there, so `cli serve` opens an")
    print("  authenticated browser without you typing anything. You need this")
    print("  token only when signing in from another device.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
