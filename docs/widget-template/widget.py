"""Copy this module into widgets/<widget_id>.py in a source checkout."""

from widgets.base import Card

WIDGET_ID = "sample_status"
WIDGET_ORDER = 90


class SampleStatusCard(Card):
    INTERVAL = 10

    def __init__(self, context):
        super().__init__("Sample status")
        self.context = context

    def tick(self):
        self.set_texts(body="Replace with your widget data")


def make_card(context):
    return SampleStatusCard(context)
