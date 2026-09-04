# Manrope — where these files came from

Vendored 2026-09-04 on the operator's ruling 4: *"vendor the OFL woff2 files
into the repo with the licence beside them — that is not the kind of binary the
no-committing instinct protects against."*

## What is here

| file | bytes | SHA-256 |
|---|---|---|
| `manrope-latin.woff2` | 24,836 | `a30ddcd349703aff7464c34bef3fffdff405ee50c113440d7c8693c02d210972` |
| `manrope-latin-ext.woff2` | 15,120 | `3911b66d9f2e005a4b989223405d0e5032619c668597ba467cc76a23c8fffcfb` |
| `OFL.txt` | 4,384 | `e01b637272e0cbdfb240184dd98ea5cc671556d9894dae2668d92ab2c906787c` |

**The hashes are the point.** A binary in a repository is checkable exactly to
the extent that its provenance is recorded, and a table nobody can reproduce is
decoration. `tools/verify.py` re-hashes both files against this table, so a
substituted font is a gate failure rather than a thing somebody notices on a
page one day.

## Where

Google Fonts, Manrope **v20**, the variable font (one weight axis, 200–800):

```
https://fonts.googleapis.com/css2?family=Manrope:wght@200..800&display=swap
```

which resolves to

```
latin      https://fonts.gstatic.com/s/manrope/v20/xn7gYHE41ni1AdIRggexSg.woff2
latin-ext  https://fonts.gstatic.com/s/manrope/v20/xn7gYHE41ni1AdIRggmxSuXd.woff2
```

The `unicode-range` declarations in `style.css` are Google's own, copied with
the files they describe rather than written by hand.

`OFL.txt` is the licence as published with the family:

```
https://raw.githubusercontent.com/google/fonts/main/ofl/manrope/OFL.txt
```

## Licence

**SIL Open Font License, Version 1.1.** Copyright 2018 The Manrope Project
Authors (https://github.com/sharanda/manrope).

The OFL permits bundling and redistribution with an application. Its conditions
that bear on this repository:

- **The licence travels with the files.** `OFL.txt` sits in this directory and
  is included in the desktop bundle by the same rule that includes the fonts.
- **The name is reserved.** The files are unmodified and are not renamed, so no
  Reserved Font Name question arises. If they are ever subsetted further, the
  result must not be called Manrope.
- **The font is not sold on its own.** It is not; it is part of an application.

## Why only two of the six subsets

Google publishes Manrope as cyrillic, cyrillic-ext, greek, vietnamese, latin
and latin-ext. This vendors the last two. Every word this interface renders is
composed in `gridiron/language.py` in English; the only text from outside is
team and fighter names, which the record stores transliterated. A character
outside the two ranges falls through to the next family in the stack, which is
what the stack is for.

## Why the variable font

`style.css` asks for **weight 640** in two places. No static instance can
answer that — it would round to 600 or 700 silently, invisible in review and
visible on the page. One variable file answers every weight the stylesheet uses
(400, 500, 600, 640, 700, 800).
