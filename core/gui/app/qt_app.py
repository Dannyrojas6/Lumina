"""Qt 应用实例工具。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication


def ensure_qt_application() -> QApplication:
    """返回当前进程唯一的 QApplication。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1] or ["lumina-gui"])
        app.setApplicationName("Lumina")
        app.setOrganizationName("Lumina")
        app.setStyle("Fusion")
    return app
