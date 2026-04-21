"""Qt GUI 共享样式。"""

from __future__ import annotations


def build_app_stylesheet() -> str:
    return """
    QWidget {
        background: #1a1a1a;
        color: #d0cfc8;
        font-size: 12px;
        font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    }

    QWidget#mainWindowCentral,
    QWidget#mainWindowPageContainer {
        background: #1a1a1a;
    }

    QLabel {
        background: transparent;
    }

    QFrame#appHeader {
        background: #111111;
        border-bottom: 1px solid #2a2a2a;
    }

    QLabel#mainWindowTitle {
        color: #e8e6de;
        font-size: 15px;
        font-weight: 600;
        padding-right: 12px;
    }

    QTabBar#topNavTabs {
        background: transparent;
    }

    QTabBar#topNavTabs::tab {
        background: transparent;
        color: #7d7d7d;
        border: 0;
        border-radius: 0;
        border-bottom: 2px solid transparent;
        padding: 4px 14px 4px 14px;
        margin-right: 4px;
        min-height: 20px;
        font-size: 14px;
        font-weight: 600;
    }

    QTabBar#topNavTabs::tab:selected {
        background: transparent;
        color: #ece8df;
        border-bottom: 2px solid #26c281;
    }

    QTabBar#topNavTabs::tab:hover:!selected {
        background: transparent;
        color: #b8b5ad;
    }

    QPushButton {
        background: #252525;
        color: #888888;
        border: 1px solid #2d2d2d;
        border-radius: 4px;
        padding: 4px 10px;
        min-height: 24px;
    }

    QPushButton:hover {
        background: #2e2e2e;
        color: #bdbab2;
    }

    QPushButton:pressed {
        background: #303030;
    }

    QPushButton:disabled {
        background: #1e1e1e;
        color: #4f4f4f;
        border-color: #252525;
    }

    QPushButton#primaryButton {
        background: #1e2e3e;
        border-color: #2a4060;
        color: #5ab0da;
    }

    QPushButton#primaryButton:hover {
        background: #223444;
        color: #7cbde0;
    }

    QPushButton#successButton {
        background: #1a3a2a;
        border-color: #2a5a3a;
        color: #4daa77;
    }

    QPushButton#successButton:hover {
        background: #1e4a32;
        color: #67c48d;
    }

    QPushButton#dangerButton {
        background: #2a1a1a;
        border-color: #4a2020;
        color: #aa5050;
    }

    QPushButton#dangerButton:hover {
        background: #341f1f;
        color: #c16b6b;
    }

    QPushButton#warningButton {
        background: #28221a;
        border-color: #4a3a20;
        color: #aa8840;
    }

    QPushButton#warningButton:hover {
        background: #342c1f;
        color: #c19c54;
    }

    QLineEdit,
    QComboBox,
    QSpinBox,
    QListWidget,
    QTextEdit,
    QPlainTextEdit {
        background: #222222;
        color: #b9b7b0;
        border: 1px solid #2d2d2d;
        border-radius: 4px;
        selection-background-color: #2d4055;
        selection-color: #e5e2da;
    }

    QLineEdit,
    QComboBox,
    QSpinBox {
        min-height: 24px;
        padding: 2px 8px;
    }

    QComboBox::drop-down,
    QSpinBox::up-button,
    QSpinBox::down-button {
        border: 0;
        background: transparent;
    }

    QComboBox[controlRole="formCombo"] {
        background: #232323;
        border: 1px solid #2d2d2d;
        border-radius: 4px;
        color: #9a9890;
        padding: 2px 10px;
        min-height: 22px;
        combobox-popup: 0;
    }

    QComboBox[controlRole="formCombo"]::drop-down {
        border: none;
        width: 14px;
    }

    QComboBox[controlRole="formCombo"]::down-arrow {
        image: none;
        width: 0;
        height: 0;
    }

    QListView[viewRole="comboPopup"] {
        background: #1f1f1f;
        color: #b9b7b0;
        border: 1px solid #2d2d2d;
        outline: 0;
        padding: 6px;
    }

    QListView[viewRole="comboPopup"]::item {
        min-height: 34px;
        padding: 0 12px;
        border-radius: 4px;
    }

    QListView[viewRole="comboPopup"]::item:selected {
        background: #2d4055;
        color: #f0ece2;
    }

    QListView[viewRole="comboPopup"]::item:hover:!selected {
        background: #262626;
        color: #d0cfc8;
    }

    QListWidget,
    QTextEdit,
    QPlainTextEdit {
        padding: 4px;
    }

    QFrame[panelRole="card"] {
        background: #1e1e1e;
        border: 1px solid #252525;
        border-radius: 7px;
    }

    QFrame[panelRole="surface"] {
        background: #141414;
        border: 1px solid #1e1e1e;
        border-radius: 7px;
    }

    QFrame[layoutRole="toolbar"] {
        background: #1e1e1e;
        border: 1px solid #252525;
        border-radius: 7px;
    }

    QFrame[layoutRole="sidePanel"] {
        background: transparent;
        border: 0;
        border-radius: 0;
    }

    QFrame[layoutRole="canvasPanel"] {
        background: #141414;
        border: 1px solid #1e1e1e;
        border-radius: 7px;
    }

    QFrame[layoutRole="editorPanel"] {
        background: #1e1e1e;
        border: 1px solid #252525;
        border-radius: 7px;
    }

    QFrame[separatorRole="divider"] {
        background: #252525;
        border: 0;
        min-height: 1px;
        max-height: 1px;
    }

    QWidget[headerRole="panel"] {
        background: #1b1b1b;
        border-bottom: 1px solid #1e1e1e;
    }

    QLabel[textRole="section"] {
        color: #8b8880;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        padding-bottom: 2px;
    }

    QLabel[textRole="panelTitle"] {
        color: #6b6b6b;
        font-size: 12px;
        font-weight: 500;
    }

    QLabel[textRole="muted"] {
        color: #777777;
        font-size: 11px;
    }

    QLabel[textRole="badge"] {
        background: #222222;
        color: #555555;
        border: 1px solid #282828;
        border-radius: 3px;
        padding: 1px 6px;
        font-size: 9px;
    }

    QLabel[textRole="mono"] {
        color: #5a7a6a;
        font-size: 9px;
        font-family: Consolas, "Cascadia Mono", monospace;
    }

    QLabel[noticeRole="saved"] {
        color: #3a5a3a;
        font-size: 10px;
    }

    QLabel[noticeRole="dirty"] {
        color: #8a7b49;
        font-size: 10px;
    }

    QLabel#runtimeStatusDot[statusState="idle"] {
        background: #444444;
        border-radius: 4px;
    }

    QLabel#runtimeStatusDot[statusState="starting"] {
        background: #5ab0da;
        border-radius: 4px;
    }

    QLabel#runtimeStatusDot[statusState="running"] {
        background: #4daa77;
        border-radius: 4px;
    }

    QLabel#runtimeStatusDot[statusState="stopped"] {
        background: #aa8840;
        border-radius: 4px;
    }

    QLabel#runtimeStatusDot[statusState="failed"] {
        background: #aa5050;
        border-radius: 4px;
    }

    QLabel#runtimeStatusValue {
        font-size: 13px;
        font-weight: 600;
    }

    QLabel#runtimeStatusValue[statusState="idle"] {
        color: #888888;
    }

    QLabel#runtimeStatusValue[statusState="starting"] {
        color: #5ab0da;
    }

    QLabel#runtimeStatusValue[statusState="running"] {
        color: #4daa77;
    }

    QLabel#runtimeStatusValue[statusState="stopped"] {
        color: #aa8840;
    }

    QLabel#runtimeStatusValue[statusState="failed"] {
        color: #aa5050;
    }

    QLabel#runtimePreviewStatusValue {
        background: #1f1f1f;
        border: 1px solid #2a2a2a;
        border-radius: 4px;
        padding: 1px 10px;
        font-size: 11px;
        font-weight: 500;
        min-width: 50px;
    }

    QLabel#runtimePreviewStatusValue[statusState="idle"] {
        color: #888888;
    }

    QLabel#runtimePreviewStatusValue[statusState="starting"] {
        color: #5ab0da;
        border-color: #2a4060;
    }

    QLabel#runtimePreviewStatusValue[statusState="running"] {
        color: #4daa77;
        border-color: #2a5a3a;
    }

    QLabel#runtimePreviewStatusValue[statusState="stopped"] {
        color: #aa8840;
        border-color: #4a3a20;
    }

    QLabel#runtimePreviewStatusValue[statusState="failed"] {
        color: #aa5050;
        border-color: #4a2020;
    }

    QLabel#runtimePreviewViewport {
        background: #141414;
        border: 0;
    }

    QTextEdit#runtimeLogOutput {
        background: #141414;
        border-top: 1px solid #1e1e1e;
        border-left: 0;
        border-right: 0;
        border-bottom: 0;
    }

    QTextEdit[editorRole="export"] {
        background: #141414;
        border: 1px solid #1e1e1e;
    }

    QLabel[previewRole="toolPreview"] {
        background: #111111;
        border: 1px solid #1e1e1e;
    }

    QPushButton[buttonRole="headerAction"] {
        padding: 0 10px;
        min-height: 0;
    }

    QPushButton[buttonRole="pillToggle"] {
        border-radius: 0;
        min-height: 24px;
        padding: 4px 8px;
    }

    QPushButton[buttonRole="pillToggle"]:checked {
        background: #1a2a3a;
        border-color: #2a4a6a;
        color: #7ab0da;
    }

    QScrollBar:vertical {
        background: #161616;
        width: 10px;
        margin: 0;
    }

    QScrollBar::handle:vertical {
        background: #2d2d2d;
        border-radius: 5px;
        min-height: 24px;
    }

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical,
    QScrollBar:horizontal,
    QScrollBar::handle:horizontal,
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {
        background: transparent;
        border: 0;
        height: 0;
        width: 0;
    }
    """
