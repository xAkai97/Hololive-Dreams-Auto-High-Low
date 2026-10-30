# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('ddddocr')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

pil_ret = collect_all('PIL')
datas += pil_ret[0]; binaries += pil_ret[1]; hiddenimports += pil_ret[2]

# Bundle runtime assets so no manual post-build copy step is required.
datas += [
    ('templates', 'templates'),
    ('locales', 'locales'),
    ('backgrounds', 'backgrounds'),
    ('assets', 'assets'),
    ('LICENSE', '.'),
    ('THIRD_PARTY_NOTICES.md', '.'),
]

hiddenimports += [
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'cv2',
    'numpy',
    'keyboard',
    'pygetwindow',
    'mss',
    'pydirectinput',
    'ddddocr',
    'numba',
    'onnxruntime',
    'auto_bot',
    'recognizer',
    'strategies',
    'strategies.base',
    'strategies.max_profit',
    'strategies.fastest_clear',
    'strategies.balanced',
    'strategies.aggressive_balanced',
    'strategies.adaptive_rush',
    'strategies.grinder',
    'strategies.custom_parametric',
    'strategies.modifiers',
    'simulation',
    'window_control',
    'reward_vision',
    'settlement',
    'challenge_reward',
    'poker_core',
    'localization',
    'ui',
    'ui.platform',
    'ui.widgets',
    'ui.dialogs',
    'ui.canvas_renderer',
    'ui.log_manager',
    'src.ui',
    'src.ui.platform',
    'src.ui.widgets',
    'src.ui.dialogs',
    'src.ui.canvas_renderer',
    'src.ui.log_manager',
]


a = Analysis(
    ['main_ui.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'scipy', 'pandas', 'matplotlib', 'fastapi', 'uvicorn', 'ddddocr.api'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Hololive-Dreams-Auto',
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
    icon=['assets/icons/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Hololive-Dreams-Auto',
)
