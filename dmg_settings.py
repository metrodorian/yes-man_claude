import os

application = "Yes Man.app"
appname = os.path.basename(application)

format = "UDZO"
size = "10M"

files = [application]
symlinks = {"Applications": "/Applications"}

icon = "resources/AppIcon.icns"

icon_locations = {
    appname: (150, 180),
    "Applications": (450, 180),
}

background = "builtin-arrow"

window_rect = ((200, 120), (600, 380))
default_view = "icon-view"
icon_size = 100
text_size = 12
