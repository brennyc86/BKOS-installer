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
    "--collect-data", "esptool",   # stub flasher JSON-bestanden meebundelen
    "--clean",
    # UPX-compressie uit: UPX-gepakte executables zijn (naast --onefile's
    # self-extracting gedrag zelf) een van de bekendste triggers voor
    # antivirus/Chrome-heuristieken bij onbekende, ongesigneerde .exe's —
    # malware gebruikt UPX vaak om zichzelf te comprimeren/verbergen, dus
    # AV-engines zijn daar extra alert op. Zonder UPX wordt het bestand iets
    # groter, maar dat weegt niet op tegen minder valse-positieven.
    "--noupx",
]

if os.path.exists("icon.ico"):
    args += ["--icon", "icon.ico"]

PyInstaller.__main__.run(args)
