#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import threading
import time
import ctypes
import subprocess
import re

# --- CoreGraphics key sending (private event source = won't affect HIDIdleTime) ---
_cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_cf = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')

_cg.CGEventSourceCreate.restype = ctypes.c_void_p
_cg.CGEventSourceCreate.argtypes = [ctypes.c_int32]
_cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
_cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
_cg.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
_cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_cf.CFRelease.argtypes = [ctypes.c_void_p]

# kCGEventSourceStateHIDSystemState = 0 → synthetic events won't reset HIDIdleTime
_EVENT_SOURCE = _cg.CGEventSourceCreate(0)

KEY_CODES = {
    'a': 0, 's': 1, 'd': 2, 'f': 3, 'h': 4, 'g': 5, 'z': 6, 'x': 7,
    'c': 8, 'v': 9, 'b': 11, 'q': 12, 'w': 13, 'e': 14, 'r': 15, 'y': 16,
    't': 17, '1': 18, '2': 19, '3': 20, '4': 21, '6': 22, '5': 23, '=': 24,
    '9': 25, '7': 26, '-': 27, '8': 28, '0': 29, ']': 30, 'o': 31, 'u': 32,
    '[': 33, 'i': 34, 'p': 35, 'l': 37, 'j': 38, "'": 39, 'k': 40, ';': 41,
    '\\': 42, ',': 43, '/': 44, 'n': 45, 'm': 46, '.': 47,
    'tab': 48, 'space': 49, '`': 50, 'backspace': 51, 'esc': 53, 'escape': 53,
    'enter': 36, 'return': 36, 'delete': 117,
    'up': 126, 'down': 125, 'left': 123, 'right': 124,
    'f1': 122, 'f2': 120, 'f3': 99,  'f4': 118, 'f5': 96,  'f6': 97,
    'f7': 98,  'f8': 100, 'f9': 101, 'f10': 109, 'f11': 103, 'f12': 111,
}

MODIFIER_FLAGS = {
    'cmd':   0x00100000,
    'shift': 0x00020000,
    'alt':   0x00080000,
    'ctrl':  0x00040000,
}


def parse_shortcut(text: str):
    parts = [p.strip().lower() for p in text.strip().split('+')]
    modifiers, key = [], None
    for part in parts:
        if part in MODIFIER_FLAGS:
            modifiers.append(part)
        elif part in KEY_CODES or len(part) == 1:
            key = part
    return modifiers, key


def press_shortcut(modifiers, key):
    if not key:
        return
    flags = 0
    for mod in modifiers:
        flags |= MODIFIER_FLAGS.get(mod, 0)
    keycode = KEY_CODES.get(key, ord(key[0]) if len(key) == 1 else 0)

    down = _cg.CGEventCreateKeyboardEvent(_EVENT_SOURCE, keycode, True)
    _cg.CGEventSetFlags(down, flags)
    _cg.CGEventPost(0, down)
    _cf.CFRelease(down)

    up = _cg.CGEventCreateKeyboardEvent(_EVENT_SOURCE, keycode, False)
    _cg.CGEventSetFlags(up, flags)
    _cg.CGEventPost(0, up)
    _cf.CFRelease(up)


# --- Accessibility ---
_appservices = ctypes.cdll.LoadLibrary(
    '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
)
_appservices.AXIsProcessTrusted.restype = ctypes.c_bool


def has_accessibility_permission() -> bool:
    try:
        return bool(_appservices.AXIsProcessTrusted())
    except Exception:
        return False


def request_accessibility_permission():
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        AXIsProcessTrustedWithOptions({'AXTrustedCheckOptionPrompt': True})
    except Exception:
        subprocess.run(['open',
                        'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'])


# --- Mouse position polling (CGGetLastMouseDelta is deprecated/broken) ---
class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


_cg.CGEventCreate.restype = ctypes.c_void_p
_cg.CGEventCreate.argtypes = [ctypes.c_void_p]
_cg.CGEventGetLocation.restype = _CGPoint
_cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]


def _mouse_position():
    e = _cg.CGEventCreate(None)
    p = _cg.CGEventGetLocation(e)
    _cf.CFRelease(e)
    return (p.x, p.y)


# --- Background poller (frontmost app + ioreg idle for keyboard detection) ---
_cache_lock = threading.Lock()
_cached_app: str = ''
_cached_ioreg_idle: float = 0.0
# Shared last-user-activity timestamp, updated by poller and mouse checker
_last_user_activity: float = time.monotonic()
_last_sent: float = 0.0


def _set_last_sent(t: float):
    global _last_sent
    _last_sent = t


def get_user_idle_seconds() -> float:
    return time.monotonic() - _last_user_activity


def get_frontmost_app() -> str:
    with _cache_lock:
        return _cached_app


def _poll_mouse():
    """High-frequency mouse-movement detection — our keystrokes don't move the mouse."""
    global _last_user_activity
    last_pos = _mouse_position()
    while True:
        pos = _mouse_position()
        if pos != last_pos:
            _last_user_activity = time.monotonic()
            last_pos = pos
        time.sleep(0.05)


def _poll_system_state():
    """Low-frequency: frontmost app + ioreg idle for keyboard-activity detection."""
    global _cached_app, _cached_ioreg_idle, _last_user_activity
    prev_ioreg = 0.0
    while True:
        try:
            out = subprocess.check_output(
                ['ioreg', '-c', 'IOHIDSystem'], stderr=subprocess.DEVNULL, timeout=2
            ).decode()
            m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
            ioreg = int(m.group(1)) / 1e9 if m else 0.0
        except Exception:
            ioreg = prev_ioreg

        # ioreg idle reset = keyboard or click activity
        if ioreg < prev_ioreg - 0.3:
            # Only count as user activity if outside our grace window
            if time.monotonic() - _last_sent > 1.5:
                _last_user_activity = time.monotonic()
        prev_ioreg = ioreg

        try:
            app = subprocess.check_output(
                ['osascript', '-e',
                 'tell application "System Events" to get name of first process whose frontmost is true'],
                stderr=subprocess.DEVNULL, timeout=2
            ).decode().strip()
        except Exception:
            app = ''

        with _cache_lock:
            _cached_app = app
            _cached_ioreg_idle = ioreg

        time.sleep(0.5)


threading.Thread(target=_poll_mouse, daemon=True).start()
threading.Thread(target=_poll_system_state, daemon=True).start()


# --- App ---
class YesManClaudeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Yes Man Claude')
        self.resizable(False, False)
        self._running = False
        self._thread = None
        self._banner = None
        self._build_ui()
        if not has_accessibility_permission():
            self.after(500, request_accessibility_permission)
        self._poll_accessibility()

    def _poll_accessibility(self):
        granted = has_accessibility_permission()
        if granted and self._banner is not None:
            self._banner.destroy()
            self._banner = None
        elif not granted and self._banner is None:
            self._show_banner()
        self.after(1000, self._poll_accessibility)

    def _show_banner(self):
        self._banner = tk.Frame(self._frame, bg='#fff3cd', pady=8, padx=10)
        self._banner.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        tk.Label(
            self._banner,
            text='Accessibility permission missing — keystrokes will not be sent.',
            bg='#fff3cd', fg='#856404', wraplength=280, justify='left'
        ).pack(side='left', fill='x', expand=True)
        ttk.Button(
            self._banner, text='Grant Access',
            command=request_accessibility_permission
        ).pack(side='right', padx=(8, 0))

    def _build_ui(self):
        pad = {'padx': 12, 'pady': 6}
        self._frame = ttk.Frame(self, padding=16)
        self._frame.grid(row=0, column=0, sticky='nsew')
        frame = self._frame

        if not has_accessibility_permission():
            self._show_banner()

        r = 1
        ttk.Label(frame, text='Shortcut 1:').grid(row=r, column=0, sticky='w', **pad)
        self._shortcut1_var = tk.StringVar(value='cmd+shift+enter')
        ttk.Entry(frame, textvariable=self._shortcut1_var, width=22).grid(row=r, column=1, sticky='ew', **pad)

        ttk.Label(frame, text='Shortcut 2:').grid(row=r+1, column=0, sticky='w', **pad)
        self._shortcut2_var = tk.StringVar(value='cmd+enter')
        ttk.Entry(frame, textvariable=self._shortcut2_var, width=22).grid(row=r+1, column=1, sticky='ew', **pad)

        ttk.Label(frame, text='Interval (seconds):').grid(row=r+2, column=0, sticky='w', **pad)
        self._interval_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(
            frame, from_=0.1, to=60.0, increment=0.1,
            textvariable=self._interval_var, width=8, format='%.1f'
        ).grid(row=r+2, column=1, sticky='w', **pad)

        ttk.Label(frame, text='Only when app focused:').grid(row=r+3, column=0, sticky='w', **pad)
        self._app_var = tk.StringVar(value='Claude')
        ttk.Entry(frame, textvariable=self._app_var, width=22).grid(row=r+3, column=1, sticky='ew', **pad)

        ttk.Label(frame, text='Pause after activity (s):').grid(row=r+4, column=0, sticky='w', **pad)
        self._idle_var = tk.DoubleVar(value=5.0)
        ttk.Spinbox(
            frame, from_=0.1, to=60.0, increment=0.5,
            textvariable=self._idle_var, width=8, format='%.1f'
        ).grid(row=r+4, column=1, sticky='w', **pad)

        self._status_var = tk.StringVar(value='Stopped')
        ttk.Label(frame, textvariable=self._status_var, foreground='gray').grid(
            row=r+5, column=0, columnspan=2, pady=(4, 8)
        )

        self._toggle_btn = ttk.Button(frame, text='▶  Start', command=self._toggle, width=18)
        self._toggle_btn.grid(row=r+6, column=0, columnspan=2, pady=(0, 4))

        self._counter_var = tk.StringVar(value='Sent: 0')
        ttk.Label(frame, textvariable=self._counter_var, foreground='gray').grid(
            row=r+7, column=0, columnspan=2
        )
        self._count = 0

    def _toggle(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        sc1 = parse_shortcut(self._shortcut1_var.get())
        sc2 = parse_shortcut(self._shortcut2_var.get())
        if not sc1[1] and not sc1[0]:
            self._status_var.set('Invalid shortcut 1')
            return
        if not sc2[1] and not sc2[0]:
            self._status_var.set('Invalid shortcut 2')
            return

        self._running = True
        self._count = 0
        self._toggle_btn.config(text='■  Stop')
        self._status_var.set('Running…')
        self._thread = threading.Thread(target=self._loop, args=(sc1, sc2), daemon=True)
        self._thread.start()

    def _stop(self):
        self._running = False
        self._toggle_btn.config(text='▶  Start')
        self._status_var.set('Stopped')

    def _loop(self, sc1, sc2):
        while self._running:
            try:
                interval = float(self._interval_var.get())
                idle_threshold = float(self._idle_var.get())
                target_app = self._app_var.get().strip()
            except (ValueError, tk.TclError):
                time.sleep(0.1)
                continue

            idle = get_user_idle_seconds()

            if idle >= idle_threshold:
                frontmost = get_frontmost_app()
                if target_app and target_app.lower() not in frontmost.lower():
                    self.after(0, self._status_var.set,
                               f'Waiting — {frontmost or "?"} in focus')
                    time.sleep(0.5)
                    continue
                press_shortcut(*sc1)
                press_shortcut(*sc2)
                _set_last_sent(time.monotonic())
                self._count += 1
                self.after(0, self._counter_var.set, f'Sent: {self._count}')
                self.after(0, self._status_var.set, f'Running — sent #{self._count}')
                time.sleep(interval)
            else:
                remaining = idle_threshold - idle
                self.after(0, self._status_var.set, f'Paused — waiting {remaining:.1f}s')
                time.sleep(0.1)


if __name__ == '__main__':
    app = YesManClaudeApp()
    app.mainloop()
