#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import threading
import time
import ctypes
import subprocess
import re
from pynput.keyboard import Key, Controller

keyboard = Controller()

_appservices = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
)
_appservices.AXIsProcessTrusted.restype = ctypes.c_bool


def get_frontmost_app() -> str:
    try:
        return subprocess.check_output(
            ["osascript", "-e",
             'tell application "System Events" to get name of first process whose frontmost is true'],
            stderr=subprocess.DEVNULL, timeout=1
        ).decode().strip()
    except Exception:
        return ""


def get_system_idle_seconds() -> float:
    """Read HIDIdleTime via ioreg — no Accessibility permission needed."""
    try:
        out = subprocess.check_output(
            ["ioreg", "-c", "IOHIDSystem"],
            stderr=subprocess.DEVNULL, timeout=1
        ).decode()
        m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
        if m:
            return int(m.group(1)) / 1e9
    except Exception:
        pass
    return 0.0


def has_accessibility_permission() -> bool:
    try:
        return bool(_appservices.AXIsProcessTrusted())
    except Exception:
        return False


def request_accessibility_permission():
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
    except Exception:
        subprocess.run([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        ])


MODIFIER_MAP = {
    "cmd": Key.cmd,
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
}

SPECIAL_KEY_MAP = {
    "enter": Key.enter,
    "space": Key.space,
    "tab": Key.tab,
    "esc": Key.esc,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
    "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
    "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
}


def parse_shortcut(text: str):
    parts = [p.strip().lower() for p in text.strip().split("+")]
    modifiers = []
    key = None
    for part in parts:
        if part in MODIFIER_MAP:
            modifiers.append(MODIFIER_MAP[part])
        elif part in SPECIAL_KEY_MAP:
            key = SPECIAL_KEY_MAP[part]
        elif len(part) == 1:
            key = part
    return modifiers, key


def press_shortcut(modifiers, key):
    for mod in modifiers:
        keyboard.press(mod)
    if key:
        keyboard.press(key)
        keyboard.release(key)
    for mod in reversed(modifiers):
        keyboard.release(mod)


class KeyRepeaterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Key Repeater")
        self.resizable(False, False)
        self._running = False
        self._thread = None
        self._banner = None
        self._build_ui()
        if not has_accessibility_permission():
            self.after(500, self._prompt_accessibility)
        self._poll_accessibility()

    def _prompt_accessibility(self):
        request_accessibility_permission()

    def _poll_accessibility(self):
        granted = has_accessibility_permission()
        if granted and self._banner is not None:
            self._banner.destroy()
            self._banner = None
        elif not granted and self._banner is None:
            self._show_banner()
        self.after(1000, self._poll_accessibility)

    def _show_banner(self):
        self._banner = tk.Frame(self._frame, bg="#fff3cd", pady=8, padx=10)
        self._banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        tk.Label(
            self._banner,
            text="Accessibility permission missing — keystrokes will not be sent.",
            bg="#fff3cd", fg="#856404", wraplength=280, justify="left"
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            self._banner, text="Grant Access",
            command=request_accessibility_permission
        ).pack(side="right", padx=(8, 0))

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        self._frame = ttk.Frame(self, padding=16)
        self._frame.grid(row=0, column=0, sticky="nsew")
        frame = self._frame

        if not has_accessibility_permission():
            self._show_banner()

        r = 1
        ttk.Label(frame, text="Shortcut 1:").grid(row=r, column=0, sticky="w", **pad)
        self._shortcut1_var = tk.StringVar(value="cmd+shift+enter")
        ttk.Entry(frame, textvariable=self._shortcut1_var, width=22).grid(row=r, column=1, sticky="ew", **pad)

        ttk.Label(frame, text="Shortcut 2:").grid(row=r+1, column=0, sticky="w", **pad)
        self._shortcut2_var = tk.StringVar(value="cmd+enter")
        ttk.Entry(frame, textvariable=self._shortcut2_var, width=22).grid(row=r+1, column=1, sticky="ew", **pad)

        ttk.Label(frame, text="Interval (seconds):").grid(row=r+2, column=0, sticky="w", **pad)
        self._interval_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(
            frame, from_=0.1, to=60.0, increment=0.1,
            textvariable=self._interval_var, width=8, format="%.1f"
        ).grid(row=r+2, column=1, sticky="w", **pad)

        ttk.Label(frame, text="Only when app focused:").grid(row=r+3, column=0, sticky="w", **pad)
        self._app_var = tk.StringVar(value="Claude")
        ttk.Entry(frame, textvariable=self._app_var, width=22).grid(row=r+3, column=1, sticky="ew", **pad)

        ttk.Label(frame, text="Pause after activity (s):").grid(row=r+4, column=0, sticky="w", **pad)
        self._idle_var = tk.DoubleVar(value=5.0)
        ttk.Spinbox(
            frame, from_=1.0, to=60.0, increment=0.5,
            textvariable=self._idle_var, width=8, format="%.1f"
        ).grid(row=r+4, column=1, sticky="w", **pad)

        self._status_var = tk.StringVar(value="Stopped")
        ttk.Label(frame, textvariable=self._status_var, foreground="gray").grid(
            row=r+5, column=0, columnspan=2, pady=(4, 8)
        )

        self._toggle_btn = ttk.Button(frame, text="▶  Start", command=self._toggle, width=18)
        self._toggle_btn.grid(row=r+6, column=0, columnspan=2, pady=(0, 4))

        self._counter_var = tk.StringVar(value="Sent: 0")
        ttk.Label(frame, textvariable=self._counter_var, foreground="gray").grid(
            row=r+7, column=0, columnspan=2
        )
        self._count = 0

    def _toggle(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        raw1 = self._shortcut1_var.get()
        raw2 = self._shortcut2_var.get()
        sc1 = parse_shortcut(raw1)
        sc2 = parse_shortcut(raw2)
        if not sc1[1] and not sc1[0]:
            self._status_var.set("Invalid shortcut 1")
            return
        if not sc2[1] and not sc2[0]:
            self._status_var.set("Invalid shortcut 2")
            return

        try:
            interval = float(self._interval_var.get())
            idle_threshold = float(self._idle_var.get())
            if interval <= 0 or idle_threshold <= 0:
                raise ValueError
        except (ValueError, tk.TclError):
            self._status_var.set("Invalid input")
            return

        target_app = self._app_var.get().strip()
        self._running = True
        self._count = 0
        self._toggle_btn.config(text="■  Stop")
        self._status_var.set(f"Running — waiting for {idle_threshold:.0f}s idle")

        self._thread = threading.Thread(
            target=self._loop, args=(sc1, sc2, interval, idle_threshold, target_app), daemon=True
        )
        self._thread.start()

    def _stop(self):
        self._running = False
        self._toggle_btn.config(text="▶  Start")
        self._status_var.set("Stopped")

    def _loop(self, sc1, sc2, interval, idle_threshold, target_app):
        while self._running:
            idle = get_system_idle_seconds()
            if idle >= idle_threshold:
                frontmost = get_frontmost_app()
                if target_app and target_app.lower() not in frontmost.lower():
                    self.after(0, self._status_var.set,
                               f"Waiting — {frontmost or '?'} in focus")
                    time.sleep(0.5)
                    continue
                press_shortcut(*sc1)
                press_shortcut(*sc2)
                self._count += 1
                self.after(0, self._counter_var.set, f"Sent: {self._count}")
                self.after(0, self._status_var.set, f"Running — sent #{self._count}")
                time.sleep(interval)
            else:
                remaining = idle_threshold - idle
                self.after(0, self._status_var.set,
                           f"Paused — waiting {remaining:.1f}s")
                time.sleep(0.1)


if __name__ == "__main__":
    app = KeyRepeaterApp()
    app.mainloop()
