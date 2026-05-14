# Yes Man Claude

A standalone macOS app that automatically sends two keyboard shortcuts in sequence at a configurable interval — but only when the system has been idle for a set amount of time *and* a target application is focused. Built to auto-confirm prompts in tools like Claude when the user has stepped away.

## Default behavior

1. Send `cmd+shift+enter`
2. Immediately send `cmd+enter`
3. Wait for the configured interval (default: 1 second)
4. Repeat — but only if the target app (default: `Claude`) is in focus and no mouse/keyboard activity has been detected for the configured idle threshold (default: 5 seconds)

## Install

### Option A — DMG (recommended)

1. Open `Yes Man Claude.dmg`
2. Drag **Yes Man Claude** into the **Applications** folder
3. Launch from Launchpad or Spotlight

### Option B — Drop the `.app` directly

Drag `Yes Man Claude.app` from this repository into `/Applications`.

The `.app` is fully self-contained (Python, Tcl/Tk and pynput are bundled — ~26 MB). No `pip install`, no Python setup needed.

## First launch — Accessibility permission

macOS requires **Accessibility** permission for global keystroke monitoring and synthesis.

1. On first launch, a yellow banner appears in the window — click **Grant Access**.
2. macOS opens **System Settings → Privacy & Security → Accessibility**.
3. Toggle **Yes Man Claude** on.
4. The banner disappears automatically within ~1 second (the app polls the permission state).

If you rebuild the app or replace the bundle, macOS treats it as a *new* binary and the old permission entry no longer applies. Remove the stale entry with the `–` button in the Accessibility list and grant access fresh.

## Settings

| Field | Description | Default |
|---|---|---|
| Shortcut 1 | First key combo sent | `cmd+shift+enter` |
| Shortcut 2 | Second key combo sent immediately after | `cmd+enter` |
| Interval (seconds) | Wait time between each send cycle | `1.0` |
| Only when app focused | App name that must be frontmost (substring match, case-insensitive) | `Claude` |
| Pause after activity (s) | Idle time required before sending resumes | `5.0` |

### Supported modifiers
`cmd`, `ctrl`, `alt`, `shift`

### Supported special keys
`enter`, `space`, `tab`, `esc`, `backspace`, `delete`, arrow keys, `f1`–`f12`, plus any single character key.

## Build from source

Requires Python 3.10+.

```bash
pip3 install py2app pynput dmgbuild

# Build the standalone .app
python3 setup.py py2app
mv "dist/Yes Man Claude.app" "Yes Man Claude.app"

# Build the DMG installer
dmgbuild -s dmg_settings.py "Yes Man Claude" "Yes Man Claude.dmg"
```

> **Note:** `setup.py` references `libffi.8.dylib`, `libtcl8.6.dylib`, and `libtk8.6.dylib` from a local miniconda install. Adjust the paths in `setup.py` if your Python ships those libraries from a different location.

## Files

- `yes_man_claude.py` — the Tk app source
- `setup.py` — py2app configuration
- `dmg_settings.py` — dmgbuild configuration
- `resources/AppIcon.icns` — app icon
- `Yes Man Claude.app` — built standalone macOS app
- `Yes Man Claude.dmg` — drag-to-Applications installer
