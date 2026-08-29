# PyInstaller onedir build for Gridiron.
#
#     .venv/Scripts/pyinstaller desktop/gridiron.spec --noconfirm
#
# onedir, not onefile: a onefile build unpacks itself to a temp directory on
# every launch, which costs seconds of startup and makes the bundled schema and
# static files harder to inspect when something is wrong. This app is a local
# tool; a visible folder of its own parts is the friendlier shape.
#
# Two things must be carried as data rather than code, because they are read
# from disk at runtime:
#   * gridiron/schema.sql  — db.init() executes it
#   * gridiron/web/*       — the API serves these as static files
#
# The database itself is NOT bundled. It lives in var/ next to the repo, or
# wherever GRIDIRON_DB points, so a rebuild never overwrites a track record.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
REPO = SPEC_DIR.parent
PACKAGE = REPO / "gridiron"

datas = [
    (str(PACKAGE / "schema.sql"), "gridiron"),
    (str(PACKAGE / "web"), "gridiron/web"),
]

# uvicorn resolves its protocol and lifespan implementations by string, so
# PyInstaller's import graph cannot see them.
hiddenimports = (
    collect_submodules("uvicorn")
    + [
        "anyio._backends._asyncio",
        "gridiron.api",
        "gridiron.views",
        "gridiron.calibration",
        "gridiron.market.lines",
    ]
)

a = Analysis(
    [str(SPEC_DIR / "launcher.py")],
    pathex=[str(REPO)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The anthropic SDK is optional at runtime: without a key the LLM pass
    # degrades with a tag, so a build that omits it still behaves correctly.
    excludes=["tkinter", "test", "pytest", "playwright"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="gridiron",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # A console is kept on purpose. The launcher's loud-failure path prints a
    # banner and a traceback, and a windowed build would throw that away and
    # leave the user with a dialog and no detail.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="gridiron",
)
