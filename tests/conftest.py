"""Shared fixtures for the test session.

One QApplication for the whole session, torn down cleanly at the end.
Leaving the application (and its widgets) alive until interpreter
shutdown is a known source of flaky non-zero exits on Windows: the
tests can all pass and the process still exits 1 while Qt tears down.
Widgets are destroyed before the application itself: deleting the
QApplication while widgets are still alive segfaults instead.
"""
import pytest


@pytest.fixture(scope="session")
def qapp():
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app
    for widget in list(app.topLevelWidgets()):
        widget.deleteLater()
    app.processEvents()
    app.closeAllWindows()
    app.processEvents()
    app.quit()
    app.processEvents()
    # Drop the reference so the C++ application is destroyed here,
    # not during module teardown at interpreter shutdown.
    del app
