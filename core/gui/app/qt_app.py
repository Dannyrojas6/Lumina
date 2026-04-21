"""Qt 应用实例工具。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.gui.app.style import build_app_stylesheet

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_ICON_PATH = REPO_ROOT / "assets" / "ui" / "app_icon.png"


def load_app_icon() -> QIcon:
    """返回 Lumina 应用图标。"""
    if not APP_ICON_PATH.is_file():
        return QIcon()
    return QIcon(str(APP_ICON_PATH))


def ensure_qt_application() -> QApplication:
    """返回当前进程唯一的 QApplication。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1] or ["lumina-gui"])
        app.setApplicationName("Lumina")
        app.setOrganizationName("Lumina")
        app.setStyle("Fusion")
        app.setStyleSheet(build_app_stylesheet())
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    return app
