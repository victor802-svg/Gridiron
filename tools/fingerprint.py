"""Print the record's substance fingerprint, for declaring a new baseline.

    python tools/fingerprint.py            # the live record
    python tools/fingerprint.py --rows 765 # over the first 765 rows only

The value goes into `config.RECORD_BASELINE` by hand, with the date. Taking a
new baseline is a deliberate act: the gate compares the record against the
declared one on every run (ruling 4 on the audit, 2026-09-05).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gridiron import config, db, fingerprint  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=None,
                        help="hash only ids up to this one (default: every row)")
    args = parser.parse_args()
    conn = db.connect()
    try:
        digest, n = fingerprint.record_hash(conn, args.rows)
        faults = fingerprint.drift(conn, config.RECORD_BASELINE)
    finally:
        conn.close()
    print(f"substance_sha256 = {digest}")
    print(f"rows = {n}")
    print(f"taken_utc = {db.utcnow()}")
    print("drift against the declared baseline: "
          + ("none" if not faults else f"{len(faults)} fault(s)"))
    for f in faults[:20]:
        print("  " + f)
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
