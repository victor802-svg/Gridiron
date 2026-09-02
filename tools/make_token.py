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


def write_env(token: str, name: str = auth.TOKEN_VAR) -> None:
    """Write a secret to .env by name, preserving anything else already there.

    `name` was added for the ntfy topic (GRIDIRON_12). Both secrets live in the
    same file for the same reason -- it sits outside the bundle, so a rebuild
    cannot delete them -- and neither is ever logged.
    """
    # FILTERED ON `name`, NOT ON THE TOKEN'S NAME.
    #
    # This line read `startswith(f"{auth.TOKEN_VAR}=")` after `name` was added,
    # so writing the ntfy topic DELETED THE ACCESS TOKEN and appended the
    # topic. The server then started and reported "no access token
    # configured", which locked the operator out of their own record until the
    # token was restored by hand.
    #
    # The parameter was added and the one line that had to change with it was
    # not -- and nothing failed at the time, because dropping a line from a
    # settings file is silent until something reads it.
    lines: list[str] = []
    if auth.ENV_FILE.exists():
        lines = [
            line
            for line in auth.ENV_FILE.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith(f"{name}=")
        ]
    lines.append(f"{name}={token}")
    auth.ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Owner-only where the OS honours it. On Windows this is advisory; the file
    # still sits in a user-profile directory, which is the real boundary.
    try:
        os.chmod(auth.ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


#: The name the push topic lives under, in the same file as the access token.
NTFY_VAR = "GRIDIRON_NTFY_TOPIC"


def _make_ntfy_topic(rotate: bool = False) -> int:
    """A random ntfy topic, written to .env and printed once.

    ANYONE HOLDING THE TOPIC CAN READ THE MESSAGES. ntfy has no accounts on the
    free tier -- the topic IS the secret, which is why it is 32 random
    characters rather than "gridiron-results", and why the messages carry
    counts and team names and nothing else. A topic somebody guesses gives them
    last night's scores, which are public; it must never give them more.
    """
    existing = config.setting(NTFY_VAR)
    if existing and not rotate:
        print(f"A push topic already exists in {auth.ENV_FILE}.")
        print("It is not printed again. To replace it: --ntfy --rotate")
        return 0

    topic = secrets.token_urlsafe(24)[:32]
    write_env(topic, NTFY_VAR)
    print()
    print("=" * 68)
    print("  PHONE PUSH TOPIC - shown once. Subscribe to it on your phone.")
    print("=" * 68)
    print()
    print(f"  {topic}")
    print()
    print("  1. Install the ntfy app (Android, iOS, or ntfy.sh in a browser).")
    print("  2. Subscribe to that topic name exactly.")
    print("  3. Results and failures arrive there.")
    print()
    print("  ANYONE WITH THIS TOPIC CAN READ THE MESSAGES. They carry counts")
    print("  and team names only -- never a probability, a line, or reasoning.")
    print(f"  written to {auth.ENV_FILE}")
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rotate", action="store_true",
                    help="replace an existing token and end every open session")
    ap.add_argument("--ntfy", action="store_true",
                    help="create the phone push topic instead of the access "
                         "token (GRIDIRON_NTFY_TOPIC)")
    args = ap.parse_args()

    if args.ntfy:
        return _make_ntfy_topic(rotate=args.rotate)

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
