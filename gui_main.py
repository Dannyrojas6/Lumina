"""Lumina Qt GUI 主程序入口。"""

from __future__ import annotations

from core.gui.app.main_window import LuminaMainWindow
from core.gui.app.qt_app import ensure_qt_application


def main() -> int:
    app = ensure_qt_application()
    window = LuminaMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
