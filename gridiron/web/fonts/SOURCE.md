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
| `barlow-condensed-700-latin.woff2` | 22,444 | `3787a5a419171630e6890cfa47c4da067474d005cd0ff8dc11ec090fdc3ee2b8` |
| `barlow-condensed-700-latin-ext.woff2` | 14,640 | `9d351bd9222bfab90f943850f8039aa73cdb40e0a6cfe4127308a48bef59d5f5` |
| `barlow-condensed-800-latin.woff2` | 22,464 | `2515494e8cc2ca07c86ea78766cfa104b796aa6ed5d66821c01d51dbb0b52bce` |
| `barlow-condensed-800-latin-ext.woff2` | 14,548 | `22539b785b3cbcee08e0722ff37fa16a18e71e4482d9078f7da79da1258e7614` |
| `OFL-barlow-condensed.txt` | 4,377 | `186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f` |
| `inter-latin.woff2` | 48,256 | `3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62` |
| `inter-latin-ext.woff2` | 85,068 | `34b9c504cab7a73e37b746343a449132e56cf7b5481af2cb81dc74dcff25c956` |
| `OFL-inter.txt` | 4,380 | `262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a` |

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

---

# Barlow Condensed — where these files came from

Vendored 2026-09-24 for the board redesign (`docs/briefs/2026-09-24-board-overnight.md`):
"condensed bold type (Barlow Condensed, with fallbacks) for team names,
scores, picks and big numbers; clean sans for everything else." Same ruling
as Manrope's: an OFL woff2 with its licence beside it is not the kind of
binary the no-committing instinct protects against.

## What is here

Two weights, 700 and 800, in the latin and latin-ext subsets — the same two
subsets Manrope ships and for the same reason. Barlow Condensed is published
as static instances, not a variable font, so each weight is its own file; the
stylesheet asks for exactly these two and no other.

## Where

Google Fonts, Barlow Condensed **v13**:

```
https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800&display=swap
```

which resolves to

```
700 latin      https://fonts.gstatic.com/s/barlowcondensed/v13/HTxwL3I-JCGChYJ8VI-L6OO_au7B46r2z3bWuQ.woff2
700 latin-ext  https://fonts.gstatic.com/s/barlowcondensed/v13/HTxwL3I-JCGChYJ8VI-L6OO_au7B46r2z3jWuZEC.woff2
800 latin      https://fonts.gstatic.com/s/barlowcondensed/v13/HTxwL3I-JCGChYJ8VI-L6OO_au7B47b1z3bWuQ.woff2
800 latin-ext  https://fonts.gstatic.com/s/barlowcondensed/v13/HTxwL3I-JCGChYJ8VI-L6OO_au7B47b1z3jWuZEC.woff2
```

The `unicode-range` declarations in `style.css` are Google's own, copied with
the files they describe.

`OFL-barlow-condensed.txt` is the licence as published with the family:

```
https://raw.githubusercontent.com/google/fonts/main/ofl/barlowcondensed/OFL.txt
```

## Licence

**SIL Open Font License, Version 1.1.** Copyright 2017 The Barlow Project
Authors (https://github.com/jpt/barlow). The same conditions as Manrope's
apply and are met the same way: the licence travels with the files, the
files are unmodified and not renamed, and the font is not sold on its own.

# Inter — where these files came from

Vendored 2026-09-25 for the visual pass (`docs/briefs/2026-09-25-board-visual.md`):
the mockup at `docs/design/gridiron-redesign.html` sets everything that is not
condensed in Inter, and the brief says port, not reinterpret. Same ruling as
Manrope's. Manrope stays vendored as the fallback.

## What is here

The variable font, weight axis 400 to 700 as Google serves it, in the latin
and latin-ext subsets -- the same two subsets Manrope ships and for the same
reason.

## Where

Google Fonts, Inter **v20**:

```
https://fonts.googleapis.com/css2?family=Inter:wght@400..700&display=swap
```

which resolves to

```
latin      https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2
latin-ext  https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa25L7SUc.woff2
```

The `unicode-range` declarations in `style.css` are Google's own, copied with
the files they describe. `OFL-inter.txt` is the licence as published with the
family (https://github.com/rsms/inter/blob/master/LICENSE.txt).
