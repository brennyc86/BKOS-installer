"""
Build script: python build.py  →  dist/BKOS_Installer.exe
Vereist: pip install pyinstaller pyserial zeroconf esptool
"""
import PyInstaller.__main__
import sys
import os

args = [
    "bkos_installer.py",
    "--onefile",
    "--windowed",
    "--name", "BKOS_Installer",
    "--add-data", f"espota.py{os.pathsep}.",
    "--collect-data", "esptool",   # stub flasher JSON-bestanden meebundelen
    "--clean",
]

if os.path.exists("icon.ico"):
    args += ["--icon", "icon.ico"]

PyInstaller.__main__.run(args)
