"""The child `tools/reconstruct_prompts.py` runs inside one commit's own code.

    python -B tools/reconstruct_prompts_child.py TREE BUILT_JSON < rows.json

TREE is a `git archive` of one commit's `gridiron` package, in a scratch
directory; this imports THAT package -- never the running checkout's -- and
asserts it did. For each row given on stdin it rebuilds the reasoning prompt
from the row's own stored factors, through that tree's
`compute.FeatureVector`, `compute.describe`, `llm.build_prompt` and
`llm.SYSTEM_PROMPT`, and writes the pieces of the request as JSON to
BUILT_JSON (a file, so nothing an old module prints can corrupt it).
It opens no database, reads no settings file (the archive has none, and the
parent strips every GRIDIRON_ setting and the model's key from its
environment), and sends nothing anywhere.

THE FEATURE VECTOR IS BUILT FROM ITS OWN FIELDS: a field one commit added
(`absent_reasons` on 24 September) is simply not passed to an older one.

AND IT SAYS WHERE A DIGIT CANNOT BE KNOWN. The prompt showed each number
rounded to four places from full precision; the row keeps six. The two can
disagree only when the stored number sits exactly halfway at the fourth
place (its fifth and sixth decimals are 5 and 0), and each such factor is
named, by that tree's own plain phrase, so the record can say so.
"""

import dataclasses
import json
import sys
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(tree))

import gridiron  # noqa: E402

here = Path(gridiron.__file__).resolve()
if not here.is_relative_to(tree):
    raise SystemExit(f"imported {here}, not the archived tree {tree}")

from gridiron import config  # noqa: E402
from gridiron.factors import compute, registry  # noqa: E402
from gridiron.model import llm  # noqa: E402

FIELDS = {f.name for f in dataclasses.fields(compute.FeatureVector)}


def _vector(stored: dict):
    given = {"sport": stored["sport"], "market_type": stored["market_type"],
             "values": dict(stored.get("values") or {}),
             "absent": list(stored.get("absent") or [])}
    for name in ("failed", "notes", "sources"):
        if name in FIELDS and stored.get(name) is not None:
            given[name] = type(stored[name])(stored[name])
    return compute.FeatureVector(**given)


def _halfway(stored: dict) -> list[str]:
    names = []
    for name, value in (stored.get("values") or {}).items():
        text = f"{float(value):.6f}"
        if text.endswith("50"):
            factor = registry.REGISTRY.get(name)
            names.append(((getattr(factor, "why", None) or "").strip()) or name)
    return names


def main() -> None:
    rows = json.loads(sys.stdin.read())
    built = []
    for row in rows:
        try:
            stored = json.loads(row["factors_json"])
            fv = _vector(stored)
            prompt = llm.build_prompt(stored["question"]["claim"],
                                      compute.describe(fv), fv.notes)
            built.append({"id": row["id"], "prompt": prompt,
                          "uncertain": _halfway(stored), "error": None})
        except Exception as exc:  # noqa: BLE001 - reported per row, by name
            built.append({"id": row["id"], "prompt": None, "uncertain": [],
                          "error": f"{type(exc).__name__}: {exc}"})
    Path(sys.argv[2]).write_text(json.dumps({
        "tree": str(tree),
        "system": llm.SYSTEM_PROMPT,
        "max_tokens": config.LLM_MAX_OUTPUT_TOKENS,
        "model": config.LLM_REASONING_MODEL,
        "rows": built,
    }), encoding="utf-8")


if __name__ == "__main__":
    main()
