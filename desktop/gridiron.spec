# PyInstaller spec for the Gridiron desktop launcher.
#
#     .venv\Scripts\pyinstaller.exe desktop\gridiron.spec --noconfirm
#
# ONEDIR, NOT ONEFILE, and the reason is not taste:
#
#   * onefile unpacks the whole bundle to a temp directory on every launch,
#     which costs seconds on a cold start and does it every single time.
#   * onefile is the shape ransomware uses — a single self-extracting binary —
#     so Defender and SmartScreen treat it with suspicion. A forecaster that
#     needs an antivirus exception to open is a forecaster nobody opens.
#   * onedir can be inspected. Somebody wondering what this program does can
#     look in the folder, which is the same reason the icon is drawn in code
#     and the frontend has no build step.
#
# WHAT IS NOT IN HERE, deliberately:
#
#   * the database. It lives in var/ beside the repository, and a rebuild
#     replaces dist/ wholesale. A record inside the bundle is a record that a
#     rebuild deletes, and the record is the one thing here that cannot be
#     regenerated from anything.
#   * .env, holding the access token. Same reason: rebuilding must not sign
#     every device out.
#
# `launcher.paths_are_outside_the_bundle()` checks both at startup and refuses
# to run if either has drifted inside, and a test asserts it independently.

import sys
from pathlib import Path

REPO = Path(SPECPATH).parent

a = Analysis(
    [str(REPO / "desktop" / "launcher.py")],
    pathex=[str(REPO)],
    binaries=[],
    # The web assets are the app's interface and must ship. They are the only
    # data files: no database, no .env, no var/.
    datas=[
        (str(REPO / "gridiron" / "web"), "gridiron/web"),
        (str(REPO / "gridiron" / "schema.sql"), "gridiron"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "gridiron.sports.nfl",
        "gridiron.sports.mlb",
        "gridiron.sports.nba",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "playwright", "PyInstaller"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Gridiron",
    debug=False,
    strip=False,
    upx=False,          # UPX is another antivirus trigger for no real gain
    console=False,      # no console window; failures use a native dialog
    icon=str(REPO / "desktop" / "gridiron.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Gridiron",
)
