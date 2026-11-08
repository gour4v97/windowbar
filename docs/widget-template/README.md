# Windows Bar widget template

Copy `widget.py` into a Windows Bar source checkout as
`widgets/<your_widget_id>.py`, then follow [`../widget-sdk.md`](../widget-sdk.md)
to register its label and enabled-by-default setting. This template is for
source contributions and forks; the installed app does not load external
widget folders.

Replace `sample_status` and the displayed text with your widget's own identity
and behavior. Keep refresh work short and move blocking work to a worker.
