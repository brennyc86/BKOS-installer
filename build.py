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
    "--icon", "icon.ico" if os.path.exists("icon.ico") else "NONE",
    "--clean",
]

# Verwijder --icon als er geen icon is
args = [a for a in args if a != "NONE" and not (a == "--icon" and "NONE" in args)]

PyInstaller.__main__.run(args)
