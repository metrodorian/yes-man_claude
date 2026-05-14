from setuptools import setup

APP = ['yes_man_claude.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'resources/AppIcon.icns',
    'arch': 'universal2',
    'plist': {
        'CFBundleName': 'Yes Man',
        'CFBundleDisplayName': 'Yes Man',
        'CFBundleIdentifier': 'com.yoummday.yesman',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': 'Required to detect the frontmost application.',
        'NSAccessibilityUsageDescription': 'Required to send keyboard shortcuts to other applications.',
    },
    'includes': ['tkinter'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
