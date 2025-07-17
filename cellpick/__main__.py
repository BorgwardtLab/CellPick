import importlib.resources
import os
import sys

from PySide6.QtCore import QFile
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QPalette, Qt
from PySide6.QtWidgets import QApplication
from qt_material import apply_stylesheet

from cellpick.app.style import STYLE_QSS
from cellpick.app.ui_main import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)

    with importlib.resources.files("cellpick.assets").joinpath("Roboto-Regular.ttf").open("rb") as f:
        font_bytes = f.read()
    font_id = QFontDatabase.addApplicationFontFromData(font_bytes)
    window = MainWindow()
    window.setStyleSheet(STYLE_QSS)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
