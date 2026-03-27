# -*- mode: python ; coding: utf-8 -*-

import sys
sys.path.insert(0, SPECPATH)

from versiyon import APP_NAME


a = Analysis(
    ['main.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[
        ('App_Icons/2.png', 'App_Icons'),
        ('App_Icons/exeIcon.ico', 'App_Icons'),
        ('Templates/supplierTemplate.xlsx', 'Templates'),
    ],
    hiddenimports=['openpyxl', 'et_xmlfile'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    icon='App_Icons/exeIcon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name=APP_NAME,
)