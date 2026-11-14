r"""Example Windows Bar plugin.

Copy this file to  %APPDATA%\Windows Bar\plugins\hello_plugin.py,
turn on Settings > General > "Load widget plugins", restart Windows Bar,
then enable "Hello" in Settings > Widgets.
"""
from datetime import datetime

from widgets.base import Card

WIDGET_ID = "hello_plugin"       # unique, lowercase letters/digits/underscore
WIDGET_LABEL = "Hello"           # name shown in Settings
WIDGET_DEFAULT = False           # enabled on first run?
WIDGET_ORDER = 500               # optional: discovery order


class HelloCard(Card):
    INTERVAL = 1                 # refresh every N dock ticks

    def __init__(self, context):
        super().__init__("Hello")
        self.context = context   # PluginContext: get_config(), tokens, logger

    def tick(self):
        return self.set_texts(body=datetime.now().strftime("%H:%M:%S"))


def make_card(context):
    return HelloCard(context)
