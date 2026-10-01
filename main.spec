# PyInstaller spec for CAT:annotation.
# Build with:  pyinstaller main.spec --noconfirm
# (or just run build.bat on Windows)
#
# Produces a --onedir build in dist/CAT-annotation/ — ship the whole folder;
# colleagues run CAT-annotation.exe from inside it. onedir launches much
# faster than --onefile, which re-extracts everything to a temp dir on
# every start.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CAT-annotation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app — no console window
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
    upx=True,
    upx_exclude=[],
    name='CAT-annotation',
)
