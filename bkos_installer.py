#!/usr/bin/env python3
"""
BKOS Installer — Flash tool voor BKOS firmware
Detecteert MCU, downloadt firmware van GitHub en flashed via serieel of WiFi.
"""

import base64
import ctypes
import hashlib
import json
import os
import re
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
import io

# ─── Optionele imports ────────────────────────────────────────────────────

try:
    import serial.tools.list_ports as list_ports
    SERIAL_OK = True
except ImportError:
    SERIAL_OK = False
    list_ports = None

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    MDNS_OK = True
except ImportError:
    MDNS_OK = False

# ─── Ingebedde afbeeldingen (PNG, base64) ───────────────────────────────

HEADER_LOGO_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAGAAAAAkCAYAAAB2UT9CAAAB1klEQVR4nOVby7HCMAy0Pa+Kd6AD"
    "KIQCKJICqOHdaYErNfBOmvEY4p9Wn5g9hiBLu5JsJ058Pv6CBY7ny8tk4Arut2vUHjNKC+CR6BFI"
    "iwIXYO+Et4AWBCIAgnROYFaiI8T4mf0jKmiLvlvzYSQuupcTw7AAksSP2kaIN0t+Do4Q3QIgyxwR"
    "tEc/chu9YqQeo1IkrUR+iV6bVQEkHPPQ83NIJkFP8n5sQRqZ6SH7tXyozRFvFfAt63iLOD+NmVo3"
    "rARL8gnl2Gnrh9XggXxC7kMqL6wIT+QTyJf4ezqoO4UipGXHy36jhuY+QAKILXwLeyA/BMazIC5K"
    "EaR22t5hJkAJFGl7Ij8EoxZEQJNVth2NVseF6SRMmG0/W8SW9jyuggjqFbCVpSjU7HmsBFUBrJ5A"
    "esx8gukcgESLZK/zQdJySDL7e+15q4T77RqXqYBeHM+Xl6cqSCH4K0sNWMdM46f8grVTWrCcD0qe"
    "31qQlFMzL6xXQ9cbMbrxW0jSiLPGZ3USRjvnqQq0fGnZbq6C0NVQBm4phOSytDe24bOhHo8kcnxC"
    "709G42IdzkW90eIC6ceMLU4csOPpliekLXa4qOQR+UDD25YfBYn5SvwLGcLeRNFaHPwD0GlguIpp"
    "81AAAAAASUVORK5CYII="
)

ICON_PNG_B64 = (
    "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"
    "jTQAAAAASUVORK5CYII="
)

# ─── Kleuren ──────────────────────────────────────────────────────────────

C_BG      = "#1a2e1e"   # donker groen tussenruimte
C_SURFACE = "#ede4c8"   # licht warm beige: panelen, header, footer
C_PANEL   = "#ddd4b0"   # iets donkerder beige: invoervelden
C_RAND    = "#8a7a50"   # warm bruin rand
C_CYAAN   = "#3a7a3a"   # donker groen accent (highlights, tabs)
C_GROEN   = "#2d7a35"   # OK groen (leesbaar op beige)
C_ROOD    = "#b83030"   # fout rood
C_AMBER   = "#9a6a00"   # amber waarschuwing
C_TEKST   = "#1e2a18"   # donker tekst op lichte achtergrond
C_DIM     = "#6a5e40"   # gedimde tekst op lichte achtergrond
C_SCHADUUW = "#4a3818"   # 3D schaduw: donker warm bruin
C_GLANS    = "#fdf9f0"   # 3D glans: licht crème
C_BTN     = "#2d6333"
C_BTN_HOV = "#3a7d40"

# ─── Firmware catalogus ───────────────────────────────────────────────────

RAW_BASE = "https://raw.githubusercontent.com"
API_BASE = "https://api.github.com"

CATALOG = {
    "BKOS-NUI": {
        "repo":   "brennyc86/BKOS-NUI",
        "branch": "main",
        "platforms": {
            "CYD 7 inch  ·  Sunton 8048S070": {
                "versie_bestand": "firmware/versie_esp32s3.txt",
                "ota_bin":        "firmware/bkos_esp32s3_8048s070.bin",
                "ser_bin":        "firmware/bkos_esp32s3_8048s070.bin",
                "chip":           "esp32s3",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "ESP32 WROOM  ·  2.8\" 2432": {
                "versie_bestand": "firmware/versie_wroom.txt",
                "ota_bin":        "firmware/bkos_esp32wroom2432.bin",
                "ser_bin":        "firmware/bkos_esp32wroom2432.bin",
                "chip":           "esp32",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "ESP32 CYD  ·  2.8\" (CYD28)": {
                "versie_bestand": "firmware/versie_cyd28.txt",
                "ota_bin":        "firmware/bkos_esp32cyd28.bin",
                "ser_bin":        "firmware/bkos_esp32cyd28.bin",
                "chip":           "esp32",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "ESP32 CYD  ·  4\" Landscape (CYD40H)": {
                "versie_bestand": "firmware/versie_cyd40h.txt",
                "ota_bin":        "firmware/bkos_esp32cyd40h.bin",
                "ser_bin":        "firmware/bkos_esp32cyd40h.bin",
                "chip":           "esp32",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "ESP32 CYD  ·  4\" Portrait (CYD40V)": {
                "versie_bestand": "firmware/versie_cyd40v.txt",
                "ota_bin":        "firmware/bkos_esp32cyd40v.bin",
                "ser_bin":        "firmware/bkos_esp32cyd40v.bin",
                "chip":           "esp32",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "Raspberry Pi Pico W  ·  2.8\" 2432": {
                "versie_bestand": "firmware/versie_pico.txt",
                "ota_bin":        None,
                "ser_bin":        "firmware/bkos_pico1w2432.uf2",
                "chip":           "pico",
                "ser_addr":       None,
                "baud":           None,
                "ota_port":       None,
            },
        },
    },
    "BKOS-blanco  (firmware kiezer)": {
        "repo":   "brennyc86/BKOS-blanco",
        "branch": "main",
        "platforms": {
            "CYD 7 inch  ·  Sunton 8048S070": {
                "versie_bestand": "firmware/versie_esp32s3.txt",
                "ota_bin":        "firmware/bkos_blanco_esp32s3.bin",
                "ser_bin":        "firmware/bkos_blanco_esp32s3.bin",
                "chip":           "esp32s3",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "ESP32 WROOM  ·  2.8\" 2432": {
                "versie_bestand": "firmware/versie_wroom.txt",
                "ota_bin":        "firmware/bkos_blanco_wroom.bin",
                "ser_bin":        "firmware/bkos_blanco_wroom.bin",
                "chip":           "esp32",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "ESP32 CYD  ·  2.8\" (CYD28)": {
                "versie_bestand": "firmware/versie_cyd28.txt",
                "ota_bin":        "firmware/bkos_blanco_cyd28.bin",
                "ser_bin":        "firmware/bkos_blanco_cyd28.bin",
                "chip":           "esp32",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "ESP32 CYD  ·  4\" Landscape (CYD40H)": {
                "versie_bestand": "firmware/versie_cyd40h.txt",
                "ota_bin":        "firmware/bkos_blanco_cyd40h.bin",
                "ser_bin":        "firmware/bkos_blanco_cyd40h.bin",
                "chip":           "esp32",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "ESP32 CYD  ·  4\" Portrait (CYD40V)": {
                "versie_bestand": "firmware/versie_cyd40v.txt",
                "ota_bin":        "firmware/bkos_blanco_cyd40v.bin",
                "ser_bin":        "firmware/bkos_blanco_cyd40v.bin",
                "chip":           "esp32",
                "ser_addr":       "0x10000",
                "baud":           "921600",
                "ota_port":       3232,
            },
            "Raspberry Pi Pico W  ·  2.8\" 2432": {
                "versie_bestand": "firmware/versie_pico.txt",
                "ota_bin":        None,
                "ser_bin":        "firmware/bkos_blanco_pico.uf2",
                "chip":           "pico",
                "ser_addr":       None,
                "baud":           None,
                "ota_port":       None,
            },
        },
    },
}

# USB VID/PID → platform hint
USB_HINTS = {
    (0x2E8A, 0x000A): "Raspberry Pi Pico W  ·  2.8\" 2432",
    (0x2E8A, 0x0003): "Raspberry Pi Pico W  ·  2.8\" 2432",
    (0x2E8A, 0x0005): "Raspberry Pi Pico W  ·  2.8\" 2432",
    (0x303A, 0x1001): "CYD 7 inch  ·  Sunton 8048S070",
    (0x303A, 0x0002): "CYD 7 inch  ·  Sunton 8048S070",
    (0x1A86, 0x55D4): "CYD 7 inch  ·  Sunton 8048S070",
    (0x10C4, 0xEA60): None,   # CP2102 — niet uniek
    (0x1A86, 0x7523): None,   # CH340 — niet uniek
}

# URL van de releases.json index voor stabiele BKOS-NUI releases
BKOS_NUI_RELEASES_URL = f"{RAW_BASE}/brennyc86/BKOS-NUI/main/firmware/releases.json"

# Mapping van platform-naam naar veld in releases.json
RELEASES_SKEY = {
    "CYD 7 inch  ·  Sunton 8048S070":        "url_s3",
    "ESP32 WROOM  ·  2.8\" 2432":            "url_wroom",
    "ESP32 CYD  ·  2.8\" (CYD28)":           "url_cyd28",
    "ESP32 CYD  ·  4\" Landscape (CYD40H)":  "url_cyd40h",
    "ESP32 CYD  ·  4\" Portrait (CYD40V)":   "url_cyd40v",
    "Raspberry Pi Pico W  ·  2.8\" 2432":    "url_pico",
}


# ─── Hoofd applicatie ─────────────────────────────────────────────────────

class BkosInstaller(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("BKOS Installer")
        self.geometry("740x640")
        self.resizable(True, True)
        self.minsize(640, 560)
        self.configure(bg=C_BG)

        self._logo_img = None   # BKOS-logo voor header
        self._wifi_devices: dict[str, str] = {}   # hostname → ip
        self._download_cache: dict[str, str] = {} # url → lokaal pad
        self._stable_url_cache: dict[str, str] = {} # versie → download-url (stabiel kanaal)
        self._beta_sha_cache: dict[str, str]   = {} # versie → commit SHA (beta kanaal)
        self._flash_thread: threading.Thread | None = None
        self._zconf: "Zeroconf | None" = None
        self._actieve_tab = 0   # 0 = serieel, 1 = wifi

        try:
            import base64 as _b64, tkinter as _tk
            _img = _tk.PhotoImage(data=ICON_PNG_B64)
            self.wm_iconphoto(True, _img)
        except Exception:
            pass

        self._logo_img = self._laad_header_logo()
        self._bouw_ui()
        self._ververs_poorten()
        self.after(400, self._haal_versie_op)   # versie ophalen na opstart

        self.after(300, self._stel_min_hoogte_in)
        if MDNS_OK:
            threading.Thread(target=self._start_mdns, daemon=True).start()

    # ─── Scherm opbouwen ─────────────────────────────────────────────────

    def _bouw_ui(self):
        s = ttk.Style(self)
        s.theme_use("default")
        s.configure("TCombobox",
            fieldbackground=C_PANEL, background=C_PANEL,
            foreground=C_TEKST, selectbackground=C_RAND,
            arrowcolor=C_CYAAN, borderwidth=0, relief="flat")
        s.map("TCombobox", fieldbackground=[("readonly", C_PANEL)])
        s.configure("Horizontal.TProgressbar",
            troughcolor=C_PANEL, background=C_CYAAN,
            thickness=12, borderwidth=0)
        s.configure("TNotebook", background=C_PANEL, borderwidth=0)
        s.configure("TNotebook.Tab",
            background=C_PANEL, foreground=C_DIM,
            padding=[12, 6], font=("Segoe UI", 9))
        s.map("TNotebook.Tab",
            background=[("selected", C_SURFACE)],
            foreground=[("selected", C_CYAAN)])

        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C_SURFACE, height=64)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        if self._logo_img:
            tk.Label(hdr, image=self._logo_img, bg=C_SURFACE).pack(
                side="left", padx=(12, 8), pady=6)
        else:
            tk.Label(hdr, text="⚓", bg=C_SURFACE, fg=C_BTN,
                font=("Segoe UI", 18)).pack(side="left", padx=(16, 6), pady=8)
        hdr_tekst = tk.Frame(hdr, bg=C_SURFACE)
        hdr_tekst.pack(side="left", pady=8)
        tk.Label(hdr_tekst, text="BKOS Installer",
            bg=C_SURFACE, fg=C_TEKST,
            font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(hdr_tekst, text="Boordcomputer installatie hulpprogramma",
            bg=C_SURFACE, fg=C_DIM,
            font=("Segoe UI", 8)).pack(anchor="w")
        # Zeilboot rechts in header (eerst packen = meest rechts)
        tk.Label(hdr, text="⛵", bg=C_SURFACE, fg=C_BTN,
            font=("Segoe UI", 26)).pack(side="right", padx=(0, 20), pady=4)
        self._lbl_verbonden = tk.Label(hdr, text="", bg=C_SURFACE,
            fg=C_GROEN, font=("Segoe UI", 9))
        self._lbl_verbonden.pack(side="right", padx=4)
        # Accentstreep onder header
        tk.Frame(self, bg=C_BTN, height=3).pack(fill="x", side="top")

        # ── Hoofdgebied ───────────────────────────────────────────────────
        main = tk.Frame(self, bg=C_BG)
        main.pack(fill="both", expand=True, padx=0)

        # Linker kolom (instellingen)
        left = tk.Frame(main, bg=C_BG, width=360)
        left.pack(side="left", fill="y", padx=(12, 6), pady=12)
        left.pack_propagate(False)
        self._left_frame = left

        # Rechter kolom (log)
        right = tk.Frame(main, bg=C_BG)
        right.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=12)

        self._bouw_links(left)
        self._bouw_rechts(right)

        # ── Footer ────────────────────────────────────────────────────────
        footer = tk.Frame(self, bg=C_SURFACE, height=56)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self._var_status = tk.StringVar(value="Gereed")
        tk.Label(footer, textvariable=self._var_status,
            bg=C_SURFACE, fg=C_DIM,
            font=("Segoe UI", 9)).pack(side="left", padx=16, pady=8)

        self._btn_install = tk.Button(footer, text="  ⬇  Installeer  ",
            bg=C_BTN, fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", cursor="hand2", padx=8, pady=6,
            activebackground=C_BTN_HOV, activeforeground="white",
            command=self._start_installatie)
        self._btn_install.pack(side="right", padx=16, pady=8)

        self._progressbar = ttk.Progressbar(footer,
            style="Horizontal.TProgressbar",
            orient="horizontal", mode="determinate", maximum=100)
        self._progressbar.pack(side="right", padx=(0, 8), pady=14, ipadx=80)

    def _bouw_links(self, parent):
        def sectie(titel):
            # 4px groene linkerbalk via outer frame
            outer = tk.Frame(parent, bg=C_BTN)
            outer.pack(fill="x", pady=(10, 0))
            # Kaart: relief="raised" geeft ingebouwde 3D (highlight + schaduw)
            card = tk.Frame(outer, bg=C_SURFACE, bd=3, relief="raised")
            card.pack(fill="x", padx=(4, 0))
            # Titelregel: donkergroen + vet
            tk.Label(card, text=titel.upper(), bg=C_SURFACE,
                fg=C_BTN, font=("Segoe UI", 8, "bold"),
                anchor="w").pack(fill="x", padx=10, pady=(4, 3))
            # Groene scheidingslijn
            tk.Frame(card, bg=C_BTN, height=1).pack(fill="x")
            # Content-zone: relief="sunken" geeft ingedrukt effect
            f = tk.Frame(card, bg=C_PANEL, bd=2, relief="sunken")
            f.pack(fill="x", padx=6, pady=(5, 6))
            return f

        def rij(parent):
            r = tk.Frame(parent, bg=C_SURFACE)
            r.pack(fill="x", padx=8, pady=4)
            return r

        def lbl(parent, tekst):
            return tk.Label(parent, text=tekst, bg=C_SURFACE,
                fg=C_DIM, font=("Segoe UI", 9), width=10, anchor="w")

        def combo(parent, var, values, width=24, state="readonly"):
            cb = ttk.Combobox(parent, textvariable=var, values=values,
                state=state, width=width)
            return cb

        # ── Firmware ──────────────────────────────────────────────────────
        fw_frame = sectie("Firmware")

        r1 = rij(fw_frame)
        lbl(r1, "Type:").pack(side="left")
        self._var_fw = tk.StringVar(value=list(CATALOG.keys())[0])
        self._cb_fw = combo(r1, self._var_fw, list(CATALOG.keys()), width=22)
        self._cb_fw.pack(side="left")
        self._cb_fw.bind("<<ComboboxSelected>>", self._on_fw_change)

        r2 = rij(fw_frame)
        lbl(r2, "Platform:").pack(side="left")
        self._var_platform = tk.StringVar()
        self._cb_platform = combo(r2, self._var_platform, [], width=27)
        self._cb_platform.pack(side="left")
        self._cb_platform.bind("<<ComboboxSelected>>", self._on_platform_change)

        r_kanaal = rij(fw_frame)
        self._var_incl_beta = tk.BooleanVar(value=False)
        self._chk_beta = tk.Checkbutton(r_kanaal,
            text="incl. ontwikkeling",
            variable=self._var_incl_beta,
            bg=C_SURFACE, fg=C_TEKST,
            selectcolor=C_PANEL,
            activebackground=C_SURFACE,
            activeforeground=C_TEKST,
            font=("Segoe UI", 9),
            command=self._on_kanaal_change)
        self._chk_beta.pack(side="left")

        r3 = rij(fw_frame)
        lbl(r3, "Versie:").pack(side="left")
        self._var_versie = tk.StringVar(value="—")
        self._cb_versie = combo(r3, self._var_versie, [], width=18)
        self._cb_versie.pack(side="left", padx=(0, 6))
        tk.Button(r3, text="↻", bg=C_RAND, fg=C_TEKST,
            relief="flat", font=("Segoe UI", 9), cursor="hand2", padx=6,
            activebackground=C_RAND, activeforeground=C_CYAAN,
            command=self._haal_versie_op).pack(side="left")

        # ── Poort ─────────────────────────────────────────────────────────
        poort_frame = sectie("Poort / Apparaat")

        tabs = ttk.Notebook(poort_frame)
        tabs.pack(fill="x", padx=12, pady=8)
        tabs.bind("<<NotebookTabChanged>>",
            lambda e: setattr(self, "_actieve_tab", tabs.index(tabs.select())))

        # Tab Serieel
        t_ser = tk.Frame(tabs, bg=C_SURFACE)
        tabs.add(t_ser, text="Serieel (USB)")

        rs = tk.Frame(t_ser, bg=C_SURFACE)
        rs.pack(fill="x", pady=4)
        lbl(rs, "Poort:").pack(side="left")
        self._var_com = tk.StringVar()
        self._cb_com = combo(rs, self._var_com, [], width=20)
        self._cb_com.pack(side="left", padx=(0, 4))
        tk.Button(rs, text="↻", bg=C_RAND, fg=C_TEKST,
            relief="flat", padx=5, cursor="hand2",
            activebackground=C_RAND, activeforeground=C_CYAAN,
            command=self._ververs_poorten).pack(side="left")
        self._lbl_mcu = tk.Label(rs, text="", bg=C_SURFACE,
            fg=C_GROEN, font=("Segoe UI", 8))
        self._lbl_mcu.pack(side="left", padx=8)
        self._cb_com.bind("<<ComboboxSelected>>", self._on_com_select)

        # Tab WiFi
        t_wifi = tk.Frame(tabs, bg=C_SURFACE)
        tabs.add(t_wifi, text="WiFi (OTA)")

        rw = tk.Frame(t_wifi, bg=C_SURFACE)
        rw.pack(fill="x", pady=4)
        lbl(rw, "Apparaat:").pack(side="left")
        self._var_wifi = tk.StringVar()
        self._cb_wifi = combo(rw, self._var_wifi, [], width=20)
        self._cb_wifi.pack(side="left", padx=(0, 4))
        tk.Button(rw, text="↻", bg=C_RAND, fg=C_TEKST,
            relief="flat", padx=5, cursor="hand2",
            activebackground=C_RAND, activeforeground=C_CYAAN,
            command=self._scan_wifi).pack(side="left")

        rw2 = tk.Frame(t_wifi, bg=C_SURFACE)
        rw2.pack(fill="x", pady=(0, 2))
        lbl(rw2, "IP/hostnaam:").pack(side="left")
        self._var_wifi_ip = tk.StringVar()
        tk.Entry(rw2, textvariable=self._var_wifi_ip,
            bg=C_PANEL, fg=C_TEKST, insertbackground=C_TEKST,
            width=22, relief="flat", font=("Consolas", 9)).pack(side="left")
        tk.Label(rw2, text="(handmatig)", bg=C_SURFACE,
            fg=C_DIM, font=("Segoe UI", 8)).pack(side="left", padx=4)

        rw3 = tk.Frame(t_wifi, bg=C_SURFACE)
        rw3.pack(fill="x", pady=(0, 4))
        lbl(rw3, "Wachtwoord:").pack(side="left")
        self._var_ota_pw = tk.StringVar(value="bkos2025")
        tk.Entry(rw3, textvariable=self._var_ota_pw,
            bg=C_PANEL, fg=C_TEKST, insertbackground=C_TEKST,
            width=14, relief="flat", font=("Consolas", 9)).pack(side="left")
        tk.Label(rw3, text="(leeg = geen wachtwoord)", bg=C_SURFACE,
            fg=C_DIM, font=("Segoe UI", 8)).pack(side="left", padx=4)

        self._wifi_notitie = tk.Label(poort_frame,
            text="ℹ Schakel OTA-push in via het OTA-scherm op het apparaat.",
            bg=C_PANEL, fg=C_AMBER, font=("Segoe UI", 8),
            wraplength=300, justify="left")
        self._wifi_notitie.pack(anchor="w", padx=12, pady=(0, 6))

        # ── MCU override ──────────────────────────────────────────────────
        mcu_frame = sectie("MCU Type override")
        ro = rij(mcu_frame)
        lbl(ro, "MCU:").pack(side="left")
        alle_platforms = [p for fw in CATALOG.values()
                          for p in fw["platforms"]]
        self._var_mcu_override = tk.StringVar(value="(automatisch)")
        self._cb_mcu = combo(ro, self._var_mcu_override,
            ["(automatisch)"] + alle_platforms, width=27)
        self._cb_mcu.pack(side="left")
        self._cb_mcu.bind("<<ComboboxSelected>>", self._on_mcu_override)
        tk.Label(mcu_frame,
            text="Overschrijft automatische detectie.",
            bg=C_PANEL, fg=C_DIM, font=("Segoe UI", 8)).pack(
            anchor="w", padx=12, pady=(0, 6))

        # Init platforms
        self._on_fw_change()

    def _bouw_rechts(self, parent):
        # Zelfde 3D kaart-structuur als sectie()
        log_outer = tk.Frame(parent, bg=C_BTN)
        log_outer.pack(fill="both", expand=True, pady=(10, 0))
        log_card = tk.Frame(log_outer, bg=C_SURFACE, bd=3, relief="raised")
        log_card.pack(fill="both", expand=True, padx=(4, 0))

        tk.Label(log_card, text="LOG", bg=C_SURFACE, fg=C_BTN,
            font=("Segoe UI", 8, "bold"), anchor="w").pack(
            fill="x", padx=10, pady=(4, 3))
        tk.Frame(log_card, bg=C_BTN, height=1).pack(fill="x")

        log_content = tk.Frame(log_card, bg=C_PANEL, bd=2, relief="sunken")
        log_content.pack(fill="both", expand=True, padx=6, pady=(5, 6))

        self._log_widget = scrolledtext.ScrolledText(log_content,
            bg=C_SURFACE, fg=C_TEKST,
            font=("Consolas", 8), relief="flat",
            state="disabled", wrap="word",
            insertbackground=C_TEKST)
        self._log_widget.pack(fill="both", expand=True, padx=8, pady=8)

        # Log tags voor kleuren
        self._log_widget.tag_config("ok",  foreground=C_GROEN)
        self._log_widget.tag_config("err", foreground=C_ROOD)
        self._log_widget.tag_config("dim", foreground=C_DIM)
        self._log_widget.tag_config("hl",  foreground=C_CYAAN)

        tk.Button(parent, text="Log wissen",
            bg=C_PANEL, fg=C_DIM, relief="flat",
            font=("Segoe UI", 8), cursor="hand2",
            activebackground=C_PANEL, activeforeground=C_TEKST,
            command=self._log_wissen).pack(anchor="e", pady=(4, 0))

    # ─── Event handlers ───────────────────────────────────────────────────

    def _on_fw_change(self, event=None):
        fw = self._var_fw.get()
        cfg = CATALOG.get(fw, {})
        platforms = list(cfg.get("platforms", {}).keys())
        self._cb_platform["values"] = platforms
        if platforms:
            self._var_platform.set(platforms[0])
        else:
            self._var_platform.set("(geen platforms beschikbaar)")
        self._var_versie.set("—")
        self._cb_versie["values"] = []
        self._stable_url_cache = {}
        self._beta_sha_cache   = {}
        # Ontwikkeling-vinkje alleen relevant voor BKOS-NUI
        if hasattr(self, "_chk_beta"):
            if fw == "BKOS-NUI":
                self._chk_beta.config(state="normal")
            else:
                self._var_incl_beta.set(False)
                self._chk_beta.config(state="disabled")
        if hasattr(self, "_log_widget"):
            self._haal_versie_op()

    def _on_platform_change(self, event=None):
        self._var_versie.set("—")
        self._cb_versie["values"] = []
        self._stable_url_cache = {}
        self._beta_sha_cache   = {}
        if hasattr(self, "_log_widget"):
            self._haal_versie_op()

    def _on_kanaal_change(self, event=None):
        self._var_versie.set("—")
        self._cb_versie["values"] = []
        self._stable_url_cache = {}
        self._beta_sha_cache   = {}
        if hasattr(self, "_log_widget"):
            self._haal_versie_op()

    def _on_mcu_override(self, event=None):
        val = self._var_mcu_override.get()
        if val != "(automatisch)":
            self._var_platform.set(val)

    def _on_com_select(self, event=None):
        label = self._var_com.get()
        self._detecteer_mcu_uit_label(label)

    def _detecteer_mcu_uit_label(self, label):
        if not SERIAL_OK:
            return
        for p in list_ports.comports():
            if p.device in label:
                hint = USB_HINTS.get((p.vid, p.pid))
                if hint:
                    self._lbl_mcu.config(text=f"✓ {hint.split('·')[0].strip()}")
                    if self._var_mcu_override.get() == "(automatisch)":
                        self._var_platform.set(hint)
                    return
                else:
                    self._lbl_mcu.config(text="")
                return
        self._lbl_mcu.config(text="")

    # ─── COM poorten ──────────────────────────────────────────────────────

    def _ververs_poorten(self):
        if not SERIAL_OK:
            self._cb_com["values"] = ["pyserial niet gevonden — pip install pyserial"]
            return
        poorten = []
        for p in sorted(list_ports.comports(), key=lambda x: x.device):
            hint = USB_HINTS.get((p.vid, p.pid))
            if hint:
                label = f"{p.device}  —  {hint.split('·')[0].strip()}"
            else:
                desc = (p.description or "onbekend")[:40]
                label = f"{p.device}  —  {desc}"
            poorten.append(label)
        self._cb_com["values"] = poorten
        if poorten:
            if not self._var_com.get() or self._var_com.get() not in poorten:
                self._var_com.set(poorten[0])
            self._detecteer_mcu_uit_label(poorten[0])
        else:
            self._var_com.set("(geen poorten gevonden)")
            self._lbl_mcu.config(text="")

    # ─── WiFi / mDNS ──────────────────────────────────────────────────────

    def _start_mdns(self):
        try:
            self._wifi_devices = {}
            self._zconf = Zeroconf()
            listener = _MdnsListener(self)
            ServiceBrowser(self._zconf, "_arduino._tcp.local.", listener)
        except Exception as e:
            self._log(f"mDNS fout: {e}", "err")

    def _scan_wifi(self):
        if not MDNS_OK:
            self._log("zeroconf niet gevonden — pip install zeroconf", "err")
            return
        self._log("Scannen op Arduino OTA-apparaten (3s)...", "dim")
        self._wifi_devices = {}
        if self._zconf:
            try:
                self._zconf.close()
            except Exception:
                pass
        threading.Thread(target=self._start_mdns, daemon=True).start()
        self.after(3000, self._ververs_wifi_lijst)

    def _ververs_wifi_lijst(self):
        items = [f"{h}  [{ip}]" for h, ip in self._wifi_devices.items()]
        self._cb_wifi["values"] = items
        if items:
            self._var_wifi.set(items[0])
            self._log(f"Gevonden: {len(items)} apparaat/apparaten", "ok")
        elif not self._var_wifi.get():
            self._var_wifi.set("")

    def _wifi_ip_uit_selectie(self):
        """Haal het IP-adres op uit de WiFi-selectie of het handmatige veld."""
        manual = self._var_wifi_ip.get().strip()
        if manual:
            return manual
        sel = self._var_wifi.get()
        if "[" in sel:
            m = re.search(r'\[(.+?)\]', sel)
            if m:
                return m.group(1)
        return sel.strip()

    # ─── Versie ophalen ───────────────────────────────────────────────────

    def _haal_versie_op(self):
        threading.Thread(target=self._versie_thread, daemon=True).start()

    def _versie_thread(self):
        fw        = self._var_fw.get()
        plat_k    = self._var_platform.get()
        incl_beta = self._var_incl_beta.get() if hasattr(self, "_var_incl_beta") else False
        cfg       = CATALOG.get(fw, {})
        plat      = cfg.get("platforms", {}).get(plat_k)
        if not plat:
            self._log(f"Geen platform voor: {plat_k}", "err")
            return

        # ── BKOS-NUI: stabiel + optioneel ontwikkeling ───────────────────
        if fw == "BKOS-NUI":
            skey         = RELEASES_SKEY.get(plat_k)
            alle_versies = []
            url_map      = {}
            sha_map      = {}

            # Stabiele releases ophalen uit releases.json
            if skey:
                self._log("Stabiele releases ophalen...", "dim")
                try:
                    with urllib.request.urlopen(BKOS_NUI_RELEASES_URL, timeout=10) as r:
                        data = json.loads(r.read().decode())
                    for entry in data.get("releases", []):
                        url_v = entry.get(skey, "")
                        if url_v:
                            v = entry["versie"]
                            alle_versies.append(v)
                            url_map[v] = url_v
                    self._log(f"{len(alle_versies)} stabiele versie(s) gevonden", "ok")
                except Exception as e:
                    self._log(f"Stabiele releases ophalen mislukt: {e}", "err")
            else:
                self._log(f"Geen releases.json sleutel voor: {plat_k}", "err")

            # Ontwikkelversies ophalen via commit history (alleen als vinkje aan)
            if incl_beta:
                bin_rel        = plat.get("ser_bin") or plat.get("ota_bin")
                versie_bestand = plat.get("versie_bestand", "")
                repo           = cfg["repo"]
                if bin_rel:
                    api_url = (f"{API_BASE}/repos/{repo}/commits"
                               f"?path={bin_rel}&per_page=20")
                    self._log("Ontwikkelversies ophalen via GitHub...", "dim")
                    try:
                        req = urllib.request.Request(
                            api_url,
                            headers={"Accept": "application/vnd.github.v3+json"})
                        with urllib.request.urlopen(req, timeout=15) as r:
                            if r.status == 403:
                                self._log("GitHub rate limit bereikt — probeer later.", "err")
                            else:
                                commits = json.loads(r.read().decode())
                                beta_cnt = 0
                                for commit in commits:
                                    sha = commit["sha"]
                                    msg = commit["commit"]["message"].split("\n")[0]
                                    m = re.search(r'\b(\d+\.\d+\.\d{6}\.\d+)\b', msg)
                                    if m:
                                        v = m.group(1)
                                    else:
                                        try:
                                            vurl = (f"{API_BASE}/repos/{repo}/contents/"
                                                    f"{versie_bestand}?ref={sha}")
                                            vreq = urllib.request.Request(
                                                vurl,
                                                headers={"Accept": "application/vnd.github.v3+json"})
                                            with urllib.request.urlopen(vreq, timeout=10) as vr:
                                                vdata = json.loads(vr.read().decode())
                                            v = base64.b64decode(vdata["content"]).decode().strip()
                                        except Exception:
                                            continue
                                    if v and v not in sha_map and v not in url_map:
                                        alle_versies.append(v)
                                        sha_map[v] = sha
                                        beta_cnt += 1
                                self._log(f"{beta_cnt} ontwikkelversie(s) gevonden", "ok")
                    except Exception as e:
                        self._log(f"Ontwikkelversies ophalen mislukt: {e}", "err")

            self._stable_url_cache = url_map
            self._beta_sha_cache   = sha_map

            # Bij incl. ontwikkeling: sorteer op versienummer nieuwste eerst
            if incl_beta and alle_versies:
                def _sleutel(v):
                    try:
                        d = v.split(".")
                        return (int(d[2]), int(d[3]), int(d[0]), int(d[1]))
                    except Exception:
                        return (0, 0, 0, 0)
                alle_versies.sort(key=_sleutel, reverse=True)

            if alle_versies:
                self.after(0, lambda vs=alle_versies: [
                    self._var_versie.set(vs[0]),
                    self._cb_versie.config(values=vs)
                ])
            else:
                self._log("Geen versies beschikbaar.", "err")
            return

        # ── Laatste build: versie.txt (voor BKOS-blanco) ─────────────────
        url = (f"{RAW_BASE}/{cfg['repo']}/{cfg['branch']}/"
               f"{plat['versie_bestand']}")
        self._log("Versie ophalen...", "dim")
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                versie = r.read().decode().strip()
            self.after(0, lambda v=versie: [
                self._var_versie.set(v),
                self._cb_versie.config(values=[v])
            ])
            self._log(f"Laatste versie: {versie}", "ok")
        except Exception as e:
            self._log(f"Versie ophalen mislukt: {e}", "err")

    # ─── Installatie starten ──────────────────────────────────────────────

    def _start_installatie(self):
        if self._flash_thread and self._flash_thread.is_alive():
            self._log("⚠ Al bezig...", "err")
            return

        # Poort bepalen
        if self._actieve_tab == 1:
            methode = "wifi"
            host = self._wifi_ip_uit_selectie()
            if not host:
                messagebox.showwarning("WiFi", "Geen WiFi-apparaat geselecteerd of IP ingevoerd.")
                return
            if not messagebox.askyesno("OTA bevestigen",
                    "Controleer: is OTA-push ingeschakeld op het apparaat?\n"
                    "(OTA-scherm → schakelaar aan)\n\n"
                    "Doorgaan?"):
                return
        else:
            methode = "serieel"
            com_label = self._var_com.get()
            host = com_label.split()[0] if com_label else ""
            if not host or "geen" in host.lower():
                messagebox.showwarning("Poort", "Geen seriële poort geselecteerd.")
                return

        # Platform en config
        fw     = self._var_fw.get()
        plat_k = self._var_platform.get()
        cfg    = CATALOG.get(fw, {})
        plat   = cfg.get("platforms", {}).get(plat_k)
        if not plat:
            messagebox.showerror("Fout", f"Geen configuratie voor '{plat_k}'.")
            return

        if plat["chip"] == "pico" and methode == "wifi":
            messagebox.showinfo("Pico W",
                "Pico W ondersteunt geen WiFi-flash.\n"
                "Gebruik de seriële modus (BOOTSEL-modus).")
            return

        self._btn_install.config(state="disabled")
        self._progressbar["value"] = 0
        self._flash_thread = threading.Thread(
            target=self._flash_thread_func,
            args=(methode, host, fw, plat_k, plat, cfg),
            daemon=True
        )
        self._flash_thread.start()

    # ─── Flash thread ─────────────────────────────────────────────────────

    def _flash_thread_func(self, methode, host, fw, plat_k, plat, cfg):
        try:
            repo    = cfg["repo"]
            branch  = cfg["branch"]
            bin_key = "ota_bin" if methode == "wifi" else "ser_bin"
            bin_rel = plat.get(bin_key)
            if not bin_rel:
                self._log(f"Geen firmware geconfigureerd voor methode '{methode}'.", "err")
                return

            versie = self._var_versie.get()

            if versie in self._stable_url_cache:
                # Stabiele release via releases.json URL
                url    = self._stable_url_cache[versie]
                naam   = url.split("/")[-1]
                lokaal = self._download(url, naam)

            elif versie in self._beta_sha_cache:
                # Ontwikkelversie via commit SHA
                sha = self._beta_sha_cache[versie]
                url = f"{RAW_BASE}/{repo}/{sha}/{bin_rel}"
                naam   = os.path.basename(bin_rel)
                lokaal = self._download(url, naam)

            else:
                # Laatste build fallback (BKOS-blanco of cache verlopen)
                url    = f"{RAW_BASE}/{repo}/{branch}/{bin_rel}"
                lokaal = self._download(url, os.path.basename(bin_rel))

            if not lokaal:
                return

            chip = plat.get("chip", "")
            if chip == "pico":
                self._flash_pico(lokaal)
            elif methode == "wifi":
                self._flash_ota(host, lokaal, plat.get("ota_port", 3232))
            else:
                self._flash_esptool(host, lokaal, plat)
        finally:
            self.after(0, lambda: self._btn_install.config(state="normal"))
            self.after(0, lambda: self._set_status("Gereed"))

    # ─── Download ─────────────────────────────────────────────────────────

    def _download(self, url, naam):
        if url in self._download_cache:
            pad = self._download_cache[url]
            if os.path.exists(pad):
                self._log(f"Cache: {naam}", "dim")
                return pad

        tmp = os.path.join(tempfile.gettempdir(), f"bkos_{naam}")
        self._log(f"Downloaden: {naam}")
        self._set_status(f"Downloaden {naam}...")
        self._set_progress(0)
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                totaal = int(resp.headers.get("Content-Length", 0) or 0)
                gedaan = 0
                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        gedaan += len(chunk)
                        if totaal:
                            self._set_progress(int(gedaan * 45 / totaal))
            kb = os.path.getsize(tmp) // 1024
            self._log(f"✓ {naam}  ({kb} KB)", "ok")
            self._download_cache[url] = tmp
            return tmp
        except Exception as e:
            self._log(f"Download mislukt: {e}", "err")
            return None

    # ─── Serieel flashing (esptool) ───────────────────────────────────────

    def _flash_esptool(self, port, firmware_pad, plat):
        chip = plat.get("chip", "esp32")
        baud = plat.get("baud", "921600")
        addr = plat.get("ser_addr", "0x10000")

        self._log(f"Serieel flashing: {port}  chip={chip}  adres={addr}")
        self._set_status(f"Flashing {port}...")
        self._set_progress(45)

        esptool_args = [
            "--chip",  chip,
            "--port",  port,
            "--baud",  baud,
            "--before", "default_reset",
            "--after",  "hard_reset",
            "write_flash", "-z", addr, firmware_pad
        ]

        if getattr(sys, "frozen", False):
            # PyInstaller .exe: gebruik module-API (stub-bestanden via --collect-data)
            try:
                import esptool
                def _voortgang(pct):
                    self._set_progress(45 + int(pct * 0.55))
                old_stdout = sys.stdout
                sys.stdout = _EsptoolCapture(self, _voortgang)
                try:
                    esptool.main(esptool_args)
                finally:
                    sys.stdout = old_stdout
                self._log("✅ Flash geslaagd!", "ok")
                self._set_progress(100)
            except SystemExit as e:
                if str(e) != "0":
                    self._log(f"esptool fout: {e}", "err")
            except Exception as e:
                self._log(f"esptool fout: {e}", "err")
        else:
            # Dev-modus: subprocess via python -m esptool
            # (vindt stub-bestanden altijd correct via module-pad)
            cmd = [sys.executable, "-m", "esptool"] + esptool_args
            ok = self._run_subprocess(cmd, 45, 55)
            if not ok:
                self._log("→ Als de poort bezet is: sluit Arduino IDE / wacht 5s en probeer opnieuw.", "dim")

    # ─── WiFi OTA flashing ────────────────────────────────────────────────

    def _flash_ota(self, host, firmware_pad, ota_port=3232):  # noqa: C901
        self._log(f"WiFi OTA → {host}:{ota_port}")
        self._set_status(f"OTA naar {host}...")
        self._set_progress(45)

        # Firmware inladen en MD5 berekenen
        try:
            with open(firmware_pad, "rb") as f:
                fw_data = f.read()
        except OSError as e:
            self._log(f"Kan firmware niet lezen: {e}", "err")
            return
        fw_size = len(fw_data)
        fw_md5  = hashlib.md5(fw_data).hexdigest()
        fw_naam = os.path.basename(firmware_pad)
        self._log(f"Firmware: {fw_size // 1024} KB  MD5: {fw_md5[:16]}...", "dim")

        # TCP server aanmaken (device verbindt terug naar ons)
        local_port = random.randint(10000, 60000)
        tcp_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            tcp_srv.bind(("", local_port))
            tcp_srv.listen(1)
        except OSError as e:
            self._log(f"TCP server aanmaken mislukt (poort {local_port}): {e}", "err")
            tcp_srv.close()
            return

        invite = f"0 {local_port} {fw_size} {fw_md5}\n"

        def _stuur_invite_en_wacht():
            """Stuurt UDP invite, retourneert antwoord-string of None bij timeout."""
            for poging in range(3):
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(5)
                try:
                    s.sendto(invite.encode(), (host, ota_port))
                    return s.recv(69).decode().strip()
                except socket.timeout:
                    if poging == 0:
                        self._log("Wachten op reactie...", "dim")
                except Exception as e:
                    self._log(f"UDP fout: {e}", "err")
                    return None
                finally:
                    s.close()
            return None

        def _authenticeer(nonce, pw, gebruik_md5_pw, oud_protocol):
            """Challenge-response authenticatie. Retourneert True bij succes."""
            cnonce_src = f"{fw_naam}{fw_size}{fw_md5}{host}"
            if oud_protocol:
                # ESP32 core 2.x: MD5 protocol (nonce = 32 chars)
                cnonce  = hashlib.md5(cnonce_src.encode()).hexdigest()
                pw_hash = hashlib.md5(pw.encode()).hexdigest()
                resp    = hashlib.md5(f"{pw_hash}:{nonce}:{cnonce}".encode()).hexdigest()
            else:
                # ESP32 core 3.x: PBKDF2-SHA256 protocol (nonce = 64 chars)
                cnonce  = hashlib.sha256(cnonce_src.encode()).hexdigest()
                pw_hash = (hashlib.md5(pw.encode()).hexdigest() if gebruik_md5_pw
                           else hashlib.sha256(pw.encode()).hexdigest())
                salt    = f"{nonce}:{cnonce}"
                derived = hashlib.pbkdf2_hmac("sha256", pw_hash.encode(), salt.encode(), 10000)
                resp    = hashlib.sha256(f"{derived.hex()}:{nonce}:{cnonce}".encode()).hexdigest()
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(10)
            try:
                s.sendto(f"200 {cnonce} {resp}\n".encode(), (host, ota_port))
                ack = s.recv(32).decode().strip()
                return ack == "OK"
            except Exception:
                return False
            finally:
                s.close()

        # ── Fase 1: invite sturen ────────────────────────────────────────────
        self._log("Uitnodiging sturen naar device...", "dim")
        data = _stuur_invite_en_wacht()
        if data is None:
            self._log("✗ Geen reactie van device.", "err")
            self._log("→ OTA-push ingeschakeld? (OTA-scherm op apparaat → schakelaar aan)", "dim")
            self._log("→ WiFi verbonden op het apparaat?", "dim")
            tcp_srv.close()
            return
        self._log(f"Device reactie: {data}", "dim")

        # ── Fase 2: authenticatie ────────────────────────────────────────────
        if data != "OK":
            if not data.startswith("AUTH "):
                self._log(f"✗ Onverwacht antwoord: {data}", "err")
                tcp_srv.close()
                return
            nonce = data.split(" ", 1)[1]
            pw    = self._var_ota_pw.get().strip()
            if not pw:
                self._log("✗ Device vraagt wachtwoord — vul OTA-wachtwoord in.", "err")
                tcp_srv.close()
                return

            if len(nonce) == 32:
                self._log("Authenticeren (MD5 protocol, core 2.x)...", "dim")
                ok_auth = _authenticeer(nonce, pw, gebruik_md5_pw=True, oud_protocol=True)
            else:
                self._log("Authenticeren (PBKDF2-SHA256, core 3.x)...", "dim")
                ok_auth = _authenticeer(nonce, pw, gebruik_md5_pw=False, oud_protocol=False)
                if not ok_auth:
                    # Fallback: opnieuw inviten en MD5 wachtwoord-hash proberen
                    self._log("SHA256 mislukt, opnieuw proberen met MD5 wachtwoord...", "dim")
                    data2 = _stuur_invite_en_wacht()
                    if data2 and data2.startswith("AUTH "):
                        nonce2  = data2.split(" ", 1)[1]
                        ok_auth = _authenticeer(nonce2, pw, gebruik_md5_pw=True, oud_protocol=False)

            if not ok_auth:
                self._log("✗ Authenticatie mislukt.", "err")
                self._log("→ Controleer OTA-wachtwoord (standaard: bkos2025).", "dim")
                tcp_srv.close()
                return
            self._log("✓ Authenticatie geslaagd.", "ok")

        # ── Fase 3: wachten op TCP-verbinding van device ─────────────────────
        self._log("Wachten op verbinding van device (max 15 s)...", "dim")
        self.after(0, lambda: self._progressbar.config(mode="indeterminate"))
        self.after(0, lambda: self._progressbar.start(10))

        tcp_srv.settimeout(15)
        conn = None
        try:
            conn, addr = tcp_srv.accept()
            self._log(f"✓ Device verbonden vanaf {addr[0]}", "ok")
        except socket.timeout:
            self._log("✗ Device kon geen TCP-verbinding maken (timeout 15 s).", "err")
            self._log("→ Windows Firewall blokkeert mogelijk inkomende verbindingen.", "dim")
            self._log("  Voeg een uitzondering toe voor python.exe of BKOS_Installer.exe.", "dim")
            return
        except Exception as e:
            self._log(f"✗ TCP accept fout: {e}", "err")
            return
        finally:
            self.after(0, lambda: self._progressbar.stop())
            self.after(0, lambda: self._progressbar.config(mode="determinate"))
            tcp_srv.close()

        # ── Fase 4: firmware uploaden in blokken van 1024 bytes ──────────────
        self._set_progress(50)
        BLOK      = 1024
        verzonden = 0
        laaste_ok = False
        conn.settimeout(10)
        try:
            while verzonden < fw_size:
                blok = fw_data[verzonden:verzonden + BLOK]
                conn.sendall(blok)
                verzonden += len(blok)
                try:
                    res = conn.recv(10).decode().strip()
                    laaste_ok = "OK" in res
                except socket.timeout:
                    self._log(f"✗ Timeout bij byte {verzonden}.", "err")
                    return
                pct = 50 + int(verzonden * 50 / fw_size)
                self._set_progress(pct)
                if verzonden % (BLOK * 32) < BLOK or verzonden >= fw_size:
                    self._log(
                        f"Upload: {verzonden * 100 // fw_size}%"
                        f"  ({verzonden // 1024}/{fw_size // 1024} KB)", "hl")

            # Eindbevestiging ophalen als laatste chunk nog geen OK gaf
            if not laaste_ok:
                conn.settimeout(30)
                for _ in range(10):
                    try:
                        res = conn.recv(32).decode().strip()
                        if "OK" in res:
                            laaste_ok = True
                            break
                    except socket.timeout:
                        continue

            if laaste_ok:
                self._log("✅ OTA upload geslaagd! Device herstart...", "ok")
            else:
                self._log("⚠ Upload voltooid — geen eindbevestiging (device herstart al).", "dim")
            self._set_progress(100)

        except Exception as e:
            self._log(f"✗ Upload fout: {e}", "err")
        finally:
            conn.close()

    # ─── Pico W UF2 flashing ─────────────────────────────────────────────

    def _flash_pico(self, firmware_pad):
        self._log("Pico W — zoek BOOTSEL-schijf (RPI-RP2)...")
        self._set_status("Zoeken naar Pico W BOOTSEL-schijf...")
        self._set_progress(45)

        schijf = self._zoek_pico_schijf()
        if not schijf:
            self._log("RPI-RP2 schijf niet gevonden.", "err")
            self._log("→ Houd BOOTSEL ingedrukt terwijl je de Pico aansluit,", "dim")
            self._log("  klik daarna opnieuw op 'Installeer'.", "dim")
            return

        self._log(f"Pico-schijf gevonden: {schijf}")
        doel = os.path.join(schijf, os.path.basename(firmware_pad))
        try:
            shutil.copy2(firmware_pad, doel)
            self._log("✅ Pico W flash geslaagd! Herstart automatisch.", "ok")
            self._set_progress(100)
        except PermissionError:
            self._log("Kopieerfout: start de installer als administrator.", "err")
        except Exception as e:
            self._log(f"Kopiëren mislukt: {e}", "err")

    def _zoek_pico_schijf(self):
        if sys.platform != "win32":
            # Linux/Mac: zoek gemount volume
            for base in ["/media", "/Volumes", "/mnt"]:
                if not os.path.isdir(base):
                    continue
                for entry in os.listdir(base):
                    info = os.path.join(base, entry, "INFO_UF2.TXT")
                    if os.path.exists(info):
                        try:
                            if "RP2040" in open(info).read():
                                return os.path.join(base, entry)
                        except Exception:
                            pass
            return None

        # Windows: loop over alle schijfletters
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if not (bitmask & 1):
                bitmask >>= 1
                continue
            bitmask >>= 1
            drive = f"{letter}:\\"
            info = os.path.join(drive, "INFO_UF2.TXT")
            if os.path.exists(info):
                try:
                    if "RP2040" in open(info).read():
                        return drive
                except Exception:
                    pass
        return None

    # ─── Subprocess helper ────────────────────────────────────────────────

    def _run_subprocess(self, cmd, pct_start, pct_range) -> bool:
        """Start subprocess, log uitvoer, geeft True terug bij succes."""
        pw = self._var_ota_pw.get()
        log_cmd = [("***" if a == pw and a else a) for a in cmd]
        self._log(f"$ {' '.join(log_cmd)}", "dim")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            laatste_lijn = ""
            for lijn in proc.stdout:
                lijn = lijn.rstrip()
                if not lijn:
                    continue
                laatste_lijn = lijn
                if any(w in lijn.lower() for w in ("error", "failed", "auth", "denied", "busy")):
                    tag = "err"
                elif any(w in lijn.lower() for w in ("writing", "uploading", "%")):
                    tag = "hl"
                else:
                    tag = ""
                self._log(lijn, tag)
                m = re.search(r'(\d+)\s*%', lijn)
                if m:
                    pct = pct_start + int(m.group(1)) * pct_range // 100
                    self._set_progress(pct)
            proc.wait()
            if proc.returncode == 0:
                self._log("✅ Geslaagd!", "ok")
                self._set_progress(100)
                return True
            else:
                self._log(f"✗ Fout (exitcode {proc.returncode})", "err")
                ll = laatste_lijn.lower()
                if "auth" in ll:
                    self._log("→ Controleer het OTA-wachtwoord.", "err")
                elif "busy" in ll or "permission" in ll or "toegang" in ll:
                    self._log("→ Poort bezet — sluit Arduino IDE / wacht 5 s en probeer opnieuw.", "err")
                return False
        except FileNotFoundError:
            self._log(f"Commando niet gevonden: {cmd[0]}", "err")
            return False
        except Exception as e:
            self._log(f"Subprocess fout: {e}", "err")
            return False

    # ─── UI helpers ───────────────────────────────────────────────────────

    def _log(self, tekst: str, tag: str = ""):
        def _do():
            self._log_widget.config(state="normal")
            ts = time.strftime("%H:%M:%S")
            if tag:
                self._log_widget.insert("end", f"[{ts}] {tekst}\n", tag)
            else:
                self._log_widget.insert("end", f"[{ts}] {tekst}\n")
            self._log_widget.see("end")
            self._log_widget.config(state="disabled")
        self.after(0, _do)

    def _log_wissen(self):
        self._log_widget.config(state="normal")
        self._log_widget.delete("1.0", "end")
        self._log_widget.config(state="disabled")

    def _set_status(self, tekst: str):
        self.after(0, lambda: self._var_status.set(tekst))

    def _set_progress(self, pct: int):
        self.after(0, lambda: self._progressbar.config(value=pct))

    def _bundle_pad(self, relatief: str) -> str:
        """Pad naar bundled bestand (werkt in .exe via _MEIPASS en in dev)."""
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, relatief)

    def _laad_header_logo(self):
        try:
            return tk.PhotoImage(data=HEADER_LOGO_B64)
        except Exception:
            return None

    def _stel_min_hoogte_in(self):
        self.update_idletasks()
        # Bereken minimum op basis van werkelijke content-hoogte linker kolom
        if hasattr(self, '_left_frame'):
            # Som van directe kinderen (de sectie-frames)
            hoogte = sum(
                w.winfo_reqheight()
                for w in self._left_frame.winfo_children()
            ) + 24  # marge boven+onder
        else:
            hoogte = 450
        min_h = hoogte + 64 + 3 + 56  # + header + streep + footer
        self.minsize(640, max(620, min_h + 40))

    def on_close(self):
        if self._zconf:
            try:
                self._zconf.close()
            except Exception:
                pass
        self.destroy()


# ─── mDNS listener ────────────────────────────────────────────────────────

if MDNS_OK:
    class _MdnsListener(ServiceListener):
        def __init__(self, app: BkosInstaller):
            self._app = app

        def add_service(self, zc: "Zeroconf", type_: str, name: str):
            info = zc.get_service_info(type_, name)
            if info and info.addresses:
                host = info.server.rstrip(".")
                ip   = socket.inet_ntoa(info.addresses[0])
                self._app._wifi_devices[host] = ip
                self._app.after(0, self._app._ververs_wifi_lijst)

        def update_service(self, zc, type_, name):
            self.add_service(zc, type_, name)

        def remove_service(self, zc, type_, name):
            host = name.split(".")[0] + ".local"
            self._app._wifi_devices.pop(host, None)
            self._app.after(0, self._app._ververs_wifi_lijst)
else:
    class _MdnsListener:
        def __init__(self, app): pass


# ─── esptool stdout capture ───────────────────────────────────────────────

class _EsptoolCapture:
    """Vangt esptool stdout op en stuurt het naar de log."""
    def __init__(self, app: BkosInstaller, voortgang_cb):
        self._app = app
        self._voortgang_cb = voortgang_cb
        self._buf = ""

    def write(self, tekst: str):
        self._buf += tekst
        while "\n" in self._buf:
            lijn, self._buf = self._buf.split("\n", 1)
            lijn = lijn.strip()
            if lijn:
                self._app._log(lijn)
            m = re.search(r'(\d+)\s*%', lijn)
            if m:
                self._voortgang_cb(int(m.group(1)))

    def flush(self):
        pass

    def fileno(self):
        raise io.UnsupportedOperation("fileno")


# ─── Entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = BkosInstaller()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
