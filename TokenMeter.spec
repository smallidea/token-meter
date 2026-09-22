# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Token Meter desktop (PySide6) on Windows.

Build from repo root:
    py -3.13 -m PyInstaller TokenMeter.spec --clean --noconfirm
Output:
    dist_desktop/TokenMeter/TokenMeter.exe  (onedir mode)
"""
from PyInstaller.utils.hooks import collect_submodules

# Force-collect every submodule of our own packages; token_meter has no
# importlib use, but being explicit avoids edge-case missing modules.
hiddenimports = []
hiddenimports += collect_submodules('token_meter')
hiddenimports += collect_submodules('custom')
hiddenimports += collect_submodules('desktop')

a = Analysis(
    ['desktop/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('desktop/resources/icon.svg', 'desktop/resources'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Desktop is a native Qt app, not the HTTP server; drop unused heavy deps.
        # Keep the stdlib-only surface token_meter relies on.
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TokenMeter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # windowed: no console window for the GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TokenMeter',
)
