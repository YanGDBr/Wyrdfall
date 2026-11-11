# PyInstaller spec for the Wyrdfall executable.
#
#     pip install pyinstaller
#     pyinstaller packaging/wyrdfall.spec
#
# Produces dist/wyrdfall.exe (Windows) or dist/wyrdfall (Linux/macOS): a
# single self-contained console binary -- the game is a terminal app, so
# it must run inside a terminal (double-clicking opens one on Windows).
# Saves go to the platformdirs user data dir, same as the pip install.

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = Path(SPECPATH).parent

datas, binaries, hiddenimports = [], [], []
for package in ("textual", "rich", "websockets", "pydantic", "networkx", "platformdirs"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
# screens are imported lazily inside handlers; make sure every one is bundled
hiddenimports += collect_submodules("wyrdfall")

a = Analysis(
    [str(project_root / "src" / "wyrdfall" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "PIL", "numpy", "scipy", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="wyrdfall",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon=None,
)
