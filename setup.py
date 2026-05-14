from setuptools import setup

APP = ['key_repeater.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'Key Repeater.app/Contents/Resources/AppIcon.icns',
    'plist': {
        'CFBundleName': 'Key Repeater',
        'CFBundleDisplayName': 'Key Repeater',
        'CFBundleIdentifier': 'com.yoummday.keyrepeater',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': 'Required to detect the frontmost application.',
        'NSSpeechRecognitionUsageDescription': '',
        'NSAccessibilityUsageDescription': 'Required to send keyboard shortcuts to other applications.',
    },
    'packages': ['pynput'],
    'includes': ['tkinter'],
    'frameworks': [
        '/Users/lennartduncker/miniconda3/lib/libffi.8.dylib',
        '/Users/lennartduncker/miniconda3/lib/libtcl8.6.dylib',
        '/Users/lennartduncker/miniconda3/lib/libtk8.6.dylib',
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
