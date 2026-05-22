"""Shared pytest fixtures for CellPick tests."""

import os

import pytest


# Ensure Qt can run in headless CI environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """Provide a single QApplication instance for GUI smoke tests."""
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    app = qtwidgets.QApplication.instance()
    if app is None:
        app = qtwidgets.QApplication([])
    return app
