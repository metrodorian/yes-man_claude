# Key Repeater

A macOS GUI app that automatically sends two keyboard shortcuts in sequence at a configurable interval, but only when the system has been idle (no mouse movement or key presses) for a set amount of time.

## Default behavior

1. Send `cmd+shift+enter`
2. Immediately send `cmd+enter`
3. Wait for the configured interval (default: 1 second)
4. Repeat — but only if no mouse or keyboard activity was detected for the configured idle threshold (default: 5 seconds)

## Requirements

- macOS
- Python 3.10+
- Dependencies: `pynput`, `Pillow` (only needed to regenerate the icon)

```bash
pip3 install pynput
```

## Usage

Double-click **Key Repeater.app** to launch.

> **Note:** macOS requires Accessibility permission for global keyboard/mouse monitoring and sending keystrokes. On first launch, click **Grant Access** in the banner and enable the app in  
> `System Settings → Privacy & Security → Accessibility`.

## Settings

| Field | Description | Default |
|---|---|---|
| Shortcut 1 | First key combo sent | `cmd+shift+enter` |
| Shortcut 2 | Second key combo sent immediately after | `cmd+enter` |
| Interval (seconds) | Wait time between each send cycle | `1.0` |
| Pause after activity (s) | Idle time required before sending resumes | `5.0` |

### Supported modifiers
`cmd`, `ctrl`, `alt`, `shift`

### Supported special keys
`enter`, `space`, `tab`, `esc`, `backspace`, `delete`, arrow keys, `f1`–`f12`, plus any single character key.
