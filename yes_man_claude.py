#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import threading
import time
import ctypes
import subprocess
import re
import os
import sys

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

# kCGEventSourceStatePrivate = -1 → events tagged as synthetic; state=1 (HID)
# detection won't see them. Verified empirically on this macOS version.
_EVENT_SOURCE = _cg.CGEventSourceCreate(-1)

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


# --- Input Monitoring (required for CGEventTap to receive HID events) ---
_iokit = ctypes.cdll.LoadLibrary(
    '/System/Library/Frameworks/IOKit.framework/IOKit'
)
try:
    _iokit.IOHIDCheckAccess.restype = ctypes.c_uint32
    _iokit.IOHIDCheckAccess.argtypes = [ctypes.c_uint32]
    _iokit.IOHIDRequestAccess.restype = ctypes.c_bool
    _iokit.IOHIDRequestAccess.argtypes = [ctypes.c_uint32]
    _HAS_HID_ACCESS_API = True
except AttributeError:
    _HAS_HID_ACCESS_API = False

# kIOHIDRequestTypeListenEvent = 1, kIOHIDAccessTypeGranted = 0
_KIO_LISTEN = 1


def has_input_monitoring_permission() -> bool:
    if not _HAS_HID_ACCESS_API:
        return True  # pre-10.15: no separate permission existed
    try:
        return _iokit.IOHIDCheckAccess(_KIO_LISTEN) == 0
    except Exception:
        return True


def request_input_monitoring_permission():
    if _HAS_HID_ACCESS_API:
        try:
            _iokit.IOHIDRequestAccess(_KIO_LISTEN)
            return
        except Exception:
            pass
    subprocess.run(['open',
                    'x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent'])


# --- User-input tracking via CGEventTap filtered by PID ---
_OUR_PID = os.getpid()
_last_user_activity: float = time.monotonic()

# Function signatures
_cg.CGEventTapCreate.restype = ctypes.c_void_p
_cg.CGEventTapCreate.argtypes = [
    ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint64,
    ctypes.c_void_p, ctypes.c_void_p
]
_cg.CGEventGetIntegerValueField.restype = ctypes.c_int64
_cg.CGEventGetIntegerValueField.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_cg.CGEventTapEnable.argtypes = [ctypes.c_void_p, ctypes.c_bool]

_cf.CFMachPortCreateRunLoopSource.restype = ctypes.c_void_p
_cf.CFMachPortCreateRunLoopSource.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32]
_cf.CFRunLoopAddSource.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_cf.CFRunLoopGetCurrent.restype = ctypes.c_void_p
_cf.CFRunLoopRun.restype = None

_kCFRunLoopCommonModes = ctypes.c_void_p.in_dll(_cf, "kCFRunLoopCommonModes")

# CGEventTapCallBack: CGEventRef (*)(proxy, type, event, refcon)
_TAP_CALLBACK_TYPE = ctypes.CFUNCTYPE(
    ctypes.c_void_p,            # return: CGEventRef
    ctypes.c_void_p,            # proxy
    ctypes.c_uint32,            # event type
    ctypes.c_void_p,            # event
    ctypes.c_void_p,            # refcon
)


def _tap_callback(proxy, event_type, event, refcon):
    try:
        # kCGEventSourceUnixProcessID = 41
        pid = _cg.CGEventGetIntegerValueField(event, 41)
        if pid != _OUR_PID:
            global _last_user_activity
            _last_user_activity = time.monotonic()
    except Exception:
        pass
    return event


_tap_callback_c = _TAP_CALLBACK_TYPE(_tap_callback)


_tap_alive = False


def is_event_tap_alive() -> bool:
    return _tap_alive


def _start_event_tap():
    global _tap_alive
    # Mask: keyDown(10), keyUp(11), mouseMoved(5), leftMouseDown(1), leftMouseUp(2),
    #       rightMouseDown(3), rightMouseDragged(6), leftMouseDragged(7), scrollWheel(22)
    mask = ((1 << 10) | (1 << 11) | (1 << 5) | (1 << 1) | (1 << 2) |
            (1 << 3) | (1 << 6) | (1 << 7) | (1 << 22))
    while True:
        if (has_accessibility_permission() and
                has_input_monitoring_permission() and
                not _tap_alive):
            # kCGHIDEventTap=0, kCGHeadInsertEventTap=0, kCGEventTapOptionListenOnly=1
            tap = _cg.CGEventTapCreate(0, 0, 1, mask, _tap_callback_c, None)
            if tap:
                source = _cf.CFMachPortCreateRunLoopSource(None, tap, 0)
                if source:
                    _cf.CFRunLoopAddSource(_cf.CFRunLoopGetCurrent(), source, _kCFRunLoopCommonModes)
                    _cg.CGEventTapEnable(tap, True)
                    _tap_alive = True
                    _cf.CFRunLoopRun()  # blocks while tap is live
                    _tap_alive = False
        time.sleep(2)


threading.Thread(target=_start_event_tap, daemon=True).start()


def get_hardware_idle_seconds() -> float:
    return time.monotonic() - _last_user_activity


# --- Background poller for frontmost app name ---
_cache_lock = threading.Lock()
_cached_app: str = ''


def get_frontmost_app() -> str:
    with _cache_lock:
        return _cached_app


def _poll_frontmost_app():
    global _cached_app
    while True:
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
        time.sleep(0.5)


threading.Thread(target=_poll_frontmost_app, daemon=True).start()


# Compatibility shim — loop calls this; no longer needed but kept harmless
def _set_last_sent(_t: float):
    pass


def _bundle_app_path():
    """Return the .app bundle path, or None when running outside a bundle."""
    res = os.environ.get('RESOURCEPATH')
    if res:
        candidate = os.path.normpath(os.path.join(res, '..', '..'))
        if candidate.endswith('.app'):
            return candidate
    p = os.path.abspath(__file__)
    while p and p != '/':
        if p.endswith('.app'):
            return p
        p = os.path.dirname(p)
    return None


# --- App ---
class YesManClaudeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Yes Man Claude')
        self.resizable(False, False)
        self._running = False
        self._thread = None
        self._banner = None
        self._banner_state = None
        self._build_ui()
        if not has_accessibility_permission():
            self.after(500, request_accessibility_permission)
        if not has_input_monitoring_permission():
            self.after(1500, request_input_monitoring_permission)
        self._poll_permissions()

    def _missing_permissions(self):
        missing = []
        if not has_accessibility_permission():
            missing.append('accessibility')
        if not has_input_monitoring_permission():
            missing.append('input_monitoring')
        return missing

    def _poll_permissions(self):
        missing = self._missing_permissions()
        if missing != self._banner_state:
            if self._banner is not None:
                self._banner.destroy()
                self._banner = None
            if missing:
                self._show_banner(missing)
            self._banner_state = missing
        self.after(1000, self._poll_permissions)

    def _show_banner(self, missing):
        self._banner = tk.Frame(self._frame, bg='#fff3cd', pady=8, padx=10)
        self._banner.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))

        if 'accessibility' in missing and 'input_monitoring' in missing:
            msg = ('Grant Accessibility & Input Monitoring, then click '
                   'Restart so macOS recognises the new permissions.')
        elif 'accessibility' in missing:
            msg = ('Accessibility permission missing — grant it, then click '
                   'Restart. Keystrokes will not be sent otherwise.')
        else:
            msg = ('Input Monitoring permission missing — grant it, then '
                   'click Restart. User activity will not be detected '
                   'otherwise.')

        tk.Label(
            self._banner, text=msg,
            bg='#fff3cd', fg='#856404', wraplength=200, justify='left'
        ).pack(side='left', fill='x', expand=True)

        btns = tk.Frame(self._banner, bg='#fff3cd')
        btns.pack(side='right')
        if 'accessibility' in missing:
            ttk.Button(btns, text='Grant Accessibility',
                       command=request_accessibility_permission
                       ).pack(fill='x')
        if 'input_monitoring' in missing:
            ttk.Button(btns, text='Grant Input Monitoring',
                       command=request_input_monitoring_permission
                       ).pack(fill='x', pady=(2, 0))
        ttk.Button(btns, text='Restart',
                   command=self._restart_app
                   ).pack(fill='x', pady=(6, 0))

    def _restart_app(self):
        app_path = _bundle_app_path()
        if app_path:
            subprocess.Popen(['open', '-n', app_path])
        self.destroy()
        sys.exit(0)

    def _build_ui(self):
        pad = {'padx': 12, 'pady': 6}
        self._frame = ttk.Frame(self, padding=16)
        self._frame.grid(row=0, column=0, sticky='nsew')
        frame = self._frame

        missing = self._missing_permissions()
        if missing:
            self._show_banner(missing)
            self._banner_state = missing

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

            idle = get_hardware_idle_seconds()

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
