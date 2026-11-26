# -*- coding: utf-8 -*-
"""
SEC-04: build the protected Kingbot application.

Steps:
  1. write integrity.json (sha256 of every core .py + data file) so the exe can verify itself at startup;
  2. run PyInstaller on packaging/kingbot.spec -> dist/Kingbot/Kingbot.exe (one folder, bytecode-compiled);
  3. create dist/Kingbot/runtime/ (KINGBOT_HOME) and drop local_config.example.json there as a starting point;
  4. copy run_protected.bat next to the exe.

Run from the Kingbot folder on a Windows machine that has Python + the bot's packages:
    python packaging/build_protected.py
    (or just double-click packaging/build_protected.bat)

The user's real runtime files (local_config.json, github_token.txt, templates/, state, logs) are NOT
put into the build - they stay on the server. Copy them into dist/Kingbot/runtime/ once, or point
KINGBOT_HOME at the existing C:\\RisBot folder, and updates of the exe will never overwrite them.
"""
import os, sys, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the Kingbot folder
sys.path.insert(0, ROOT)
import kb_integrity                                                    # noqa: E402


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    os.chdir(ROOT)
    print("1) integrity manifest")
    out, n = kb_integrity.build_manifest(
        code_dir=ROOT, out=os.path.join(ROOT, "integrity.json"),
        patterns=(".py",), extra=("ocr.ps1", "ocr_boxes.ps1", "version.json"))
    print(f"   {out} ({n} files)")

    print("2) PyInstaller")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("   PyInstaller is not installed. Run: pip install pyinstaller")
        return 1
    run([sys.executable, "-m", "PyInstaller", os.path.join("packaging", "kingbot.spec"), "--noconfirm", "--clean"])

    dist = os.path.join(ROOT, "dist", "Kingbot")
    runtime = os.path.join(dist, "runtime")
    os.makedirs(runtime, exist_ok=True)
    ex = os.path.join(ROOT, "local_config.example.json")
    if os.path.exists(ex) and not os.path.exists(os.path.join(runtime, "local_config.json")):
        shutil.copy2(ex, os.path.join(runtime, "local_config.example.json"))
    bat = os.path.join(ROOT, "packaging", "run_protected.bat")
    if os.path.exists(bat):
        shutil.copy2(bat, os.path.join(dist, "run_protected.bat"))

    print("\nDone. The protected build is in:", dist)
    print("Next: copy local_config.json, github_token.txt and your templates/ into:", runtime)
    print("Then start it with run_protected.bat (or install_service.bat to run it in the background).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
