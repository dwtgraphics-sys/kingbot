# -*- mode: python ; coding: utf-8 -*-
"""
SEC-04: PyInstaller spec for the protected Kingbot build.

  * one-folder build (not one-file): starts faster and lets the runtime/ folder sit beside the exe.
  * Python source is shipped as COMPILED BYTECODE (optimize=2 strips docstrings/asserts); the plain
    .py files are not placed next to the exe, so the logic is not casually readable or editable.
  * data files the bot needs at runtime (builtin_templates, ocr scripts, version.json) are bundled.
  * integrity.json is bundled so the startup check can verify the build has not been tampered with.

Build it from the Kingbot folder (see build_protected.py / build_protected.bat):
    pyinstaller packaging/kingbot.spec --noconfirm
"""
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.getcwd())

datas = [(p, dst) for p, dst in [
    ("builtin_templates", "builtin_templates"),
    ("ocr.ps1", "."), ("ocr_boxes.ps1", "."),
    ("version.json", "."),
    ("local_config.example.json", "."),
    ("integrity.json", "."),
] if os.path.exists(os.path.join(ROOT, p.split(os.sep)[0]))]

hiddenimports = (collect_submodules("cv2") + collect_submodules("numpy")
                 + ["pyautogui", "PIL", "PIL.ImageGrab"])

a = Analysis(
    ["packaging/kingbot_app.py"],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter", "pytest", "unittest"],
    noarchive=False,
    optimize=2,                      # compile .py -> optimized bytecode, drop docstrings
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Kingbot",
    console=True,
    icon=os.path.join(ROOT, "packaging", "kingbot.ico") if os.path.exists(os.path.join(ROOT, "packaging", "kingbot.ico")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Kingbot")
