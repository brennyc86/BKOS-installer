#!/usr/bin/env python3
"""
BKOS Installer — Flash tool voor BKOS firmware
Detecteert MCU, downloadt firmware van GitHub en flashed via serieel of WiFi.
"""

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

# ─── Kleuren ──────────────────────────────────────────────────────────────

C_BG      = "#0d1117"
C_SURFACE = "#161b22"
C_PANEL   = "#1c2128"
C_RAND    = "#30363d"
C_CYAAN   = "#00d4ff"
C_GROEN   = "#3fb950"
C_ROOD    = "#f85149"
C_AMBER   = "#d29922"
C_TEKST   = "#c9d1d9"
C_DIM     = "#6e7681"
C_BTN     = "#238636"
C_BTN_HOV = "#2ea043"

# ─── Firmware catalogus ───────────────────────────────────────────────────

RAW_BASE = "https://raw.githubusercontent.com"
API_BASE = "https://api.github.com"

CATALOG = {
    "BKOS-NUI": {
        "repo":   "brennyc86/BKOS-NUI",
        "branch": "main",
        "platforms": {
            "ESP32-S3  ·  Sunton 8048S070": {
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
    "BKOS-BASE  (toekomstig)": {
        "repo":     "brennyc86/BKOS-NUI",
        "branch":   "main",
        "platforms": {},
    },
}

# USB VID/PID → platform hint
USB_HINTS = {
    (0x2E8A, 0x000A): "Raspberry Pi Pico W  ·  2.8\" 2432",
    (0x2E8A, 0x0003): "Raspberry Pi Pico W  ·  2.8\" 2432",
    (0x2E8A, 0x0005): "Raspberry Pi Pico W  ·  2.8\" 2432",
    (0x303A, 0x1001): "ESP32-S3  ·  Sunton 8048S070",
    (0x303A, 0x0002): "ESP32-S3  ·  Sunton 8048S070",
    (0x1A86, 0x55D4): "ESP32-S3  ·  Sunton 8048S070",
    (0x10C4, 0xEA60): None,   # CP2102 — niet uniek
    (0x1A86, 0x7523): None,   # CH340 — niet uniek
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

        self._wifi_devices: dict[str, str] = {}   # hostname → ip
        self._download_cache: dict[str, str] = {} # url → lokaal pad
        self._flash_thread: threading.Thread | None = None
        self._zconf: "Zeroconf | None" = None
        self._actieve_tab = 0   # 0 = serieel, 1 = wifi

        try:
            self.iconbitmap(self._bundle_pad("assets/icon.ico"))
        except Exception:
            pass

        self._bouw_ui()
        self._ververs_poorten()
        self.after(400, self._haal_versie_op)   # versie ophalen na opstart

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
        s.configure("TNotebook", background=C_BG, borderwidth=0)
        s.configure("TNotebook.Tab",
            background=C_PANEL, foreground=C_DIM,
            padding=[12, 6], font=("Segoe UI", 9))
        s.map("TNotebook.Tab",
            background=[("selected", C_SURFACE)],
            foreground=[("selected", C_CYAAN)])

        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C_SURFACE, height=48)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⚓  BKOS Installer",
            bg=C_SURFACE, fg=C_CYAAN,
            font=("Segoe UI", 13, "bold")).pack(side="left", padx=16, pady=10)
        self._lbl_verbonden = tk.Label(hdr, text="", bg=C_SURFACE,
            fg=C_GROEN, font=("Segoe UI", 9))
        self._lbl_verbonden.pack(side="right", padx=16)

        # ── Hoofdgebied ───────────────────────────────────────────────────
        main = tk.Frame(self, bg=C_BG)
        main.pack(fill="both", expand=True, padx=0)

        # Linker kolom (instellingen)
        left = tk.Frame(main, bg=C_BG, width=360)
        left.pack(side="left", fill="y", padx=(12, 6), pady=12)
        left.pack_propagate(False)

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
            tk.Label(parent, text=titel.upper(), bg=C_BG,
                fg=C_DIM, font=("Segoe UI", 8, "bold")).pack(
                anchor="w", pady=(12, 2))
            f = tk.Frame(parent, bg=C_SURFACE,
                highlightbackground=C_RAND, highlightthickness=1)
            f.pack(fill="x")
            return f

        def rij(parent):
            r = tk.Frame(parent, bg=C_SURFACE)
            r.pack(fill="x", padx=12, pady=6)
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
            bg=C_SURFACE, fg=C_AMBER, font=("Segoe UI", 8),
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
            bg=C_SURFACE, fg=C_DIM, font=("Segoe UI", 8)).pack(
            anchor="w", padx=12, pady=(0, 6))

        # Init platforms
        self._on_fw_change()

    def _bouw_rechts(self, parent):
        tk.Label(parent, text="LOG", bg=C_BG,
            fg=C_DIM, font=("Segoe UI", 8, "bold")).pack(anchor="w")

        log_frame = tk.Frame(parent, bg=C_SURFACE,
            highlightbackground=C_RAND, highlightthickness=1)
        log_frame.pack(fill="both", expand=True, pady=(2, 0))

        self._log_widget = scrolledtext.ScrolledText(log_frame,
            bg=C_SURFACE, fg=C_TEKST,
            font=("Consolas", 8), relief="flat",
            state="disabled", wrap="word",
            insertbackground=C_TEKST)
        self._log_widget.pack(fill="both", expand=True, padx=6, pady=6)

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
        if hasattr(self, "_log_widget"):
            self._haal_versie_op()

    def _on_platform_change(self, event=None):
        self._var_versie.set("—")
        self._cb_versie["values"] = []
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
        fw      = self._var_fw.get()
        plat_k  = self._var_platform.get()
        cfg     = CATALOG.get(fw, {})
        plat    = cfg.get("platforms", {}).get(plat_k)
        if not plat:
            self._log(f"Geen platform voor: {plat_k}", "err")
            return
        url = (f"{RAW_BASE}/{cfg['repo']}/{cfg['branch']}/"
               f"{plat['versie_bestand']}")
        self._log(f"Versie ophalen...", "dim")
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
            repo   = cfg["repo"]
            branch = cfg["branch"]
            bin_key = "ota_bin" if methode == "wifi" else "ser_bin"
            bin_rel = plat.get(bin_key)
            if not bin_rel:
                self._log(f"Geen firmware geconfigureerd voor methode '{methode}'.", "err")
                return

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

    def _flash_ota(self, host, firmware_pad, ota_port=3232):
        self._log(f"WiFi OTA → {host}:{ota_port}")
        self._set_status(f"OTA naar {host}...")
        self._set_progress(45)

        # Controleer eerst of het device bereikbaar is op de OTA-poort (UDP)
        self._log("Verbinding testen...", "dim")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            sock.connect((host, ota_port))
            sock.close()
        except OSError as e:
            self._log(f"✗ Device niet bereikbaar op {host}:{ota_port} — {e}", "err")
            self._log("→ Controleer: WiFi verbonden? OTA-push ingeschakeld op het apparaat?", "dim")
            return

        espota_pad = self._bundle_pad("espota.py")
        if not os.path.exists(espota_pad):
            self._log("espota.py niet gevonden naast de installer.", "err")
            return

        cmd = [sys.executable, espota_pad,
               "--ip", host,
               "--port", str(ota_port),
               "--file", firmware_pad,
               "--progress"]

        pw = self._var_ota_pw.get().strip()
        if pw:
            cmd += ["--auth", pw]

        ok = self._run_subprocess(cmd, 45, 55)
        if not ok:
            self._log("→ Mogelijke oorzaken: OTA-push uitgeschakeld, verkeerd wachtwoord, of device heeft geen geheugen vrij.", "dim")

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
