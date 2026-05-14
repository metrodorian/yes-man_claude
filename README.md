# Yes Man

A standalone macOS app that automatically sends two keyboard shortcuts in sequence at a configurable interval — but only when the system has been idle for a set amount of time *and* a target application is focused. Built to auto-confirm prompts in tools like Claude when the user has stepped away.

## Default behavior

1. Send `cmd+shift+enter`
2. Immediately send `cmd+enter`
3. Wait for the configured interval (default: 1 second)
4. Repeat — but only if the target app (default: `Claude`) is in focus and no mouse/keyboard activity has been detected for the configured idle threshold (default: 5 seconds)

## Install

### Option A — DMG (recommended)

1. Open `Yes Man.dmg`
2. Drag **Yes Man** into the **Applications** folder
3. Launch from Launchpad or Spotlight

### Option B — Drop the `.app` directly

Drag `Yes Man.app` from this repository into `/Applications`.

The `.app` is fully self-contained — a **universal2 build** (runs natively on Apple Silicon *and* Intel) with **Python 3.13 and Tcl/Tk bundled inside the app** (~62 MB unpacked, ~26 MB DMG). No Python install, no Homebrew, no `pip install` needed.

## First launch — Accessibility permission

macOS requires **Accessibility** permission for the app to read global input idle state and send keyboard shortcuts.

1. On first launch, a yellow banner appears in the window — click **Grant Access**.
2. macOS opens **System Settings → Privacy & Security → Accessibility**.
3. Toggle **Yes Man** on.
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

Requires the **universal2 Python from [python.org](https://www.python.org/downloads/macos/)** installed under `/Library/Frameworks/Python.framework/` (Homebrew/conda Pythons are single-architecture and will produce a non-universal bundle).

```bash
PY=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3
$PY -m pip install py2app dmgbuild

# Build the standalone .app (universal2)
$PY setup.py py2app
mv "dist/Yes Man.app" "Yes Man.app"

# Build the DMG installer
$PY -m dmgbuild -s dmg_settings.py "Yes Man" "Yes Man.dmg"
```

Verify the build is universal2:

```bash
file "Yes Man.app/Contents/MacOS/Yes Man"
# → Mach-O universal binary with 2 architectures: [x86_64] [arm64]
```

## Files

- `yes_man_claude.py` — the Tk app source
- `setup.py` — py2app configuration (`arch: universal2`)
- `dmg_settings.py` — dmgbuild configuration
- `resources/AppIcon.icns` — app icon
- `Yes Man.app` — built standalone macOS app (universal2, ~62 MB)
- `Yes Man.dmg` — drag-to-Applications installer (~26 MB)
