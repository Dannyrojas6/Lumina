"""Lumina 单窗口工作台。"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from core.gui.runtime.controller import AutomationRuntimeController, RuntimeController
from core.gui.runtime.runtime_page import RuntimePage
from core.gui.tools.coordinate_page import CoordinateToolPage
from core.gui.tools.custom_sequence_page import CustomSequencePage
from core.gui.tools.mask_region_page import MaskRegionToolPage


def compute_initial_window_geometry(
    *,
    available_x: int,
    available_y: int,
    available_width: int,
    available_height: int,
    scale_factor: float,
) -> tuple[int, int, int, int]:
    """按物理目标尺寸 1920x1080 折算出 Qt 逻辑窗口尺寸，并居中。"""
    normalized_scale = scale_factor if scale_factor > 0 else 1.0
    target_width = int(round(1920 / normalized_scale))
    target_height = int(round(1080 / normalized_scale))
    width = min(target_width, available_width)
    height = min(target_height, available_height)
    x = available_x + max((available_width - width) // 2, 0)
    y = available_y + max((available_height - height) // 2, 0)
    return (x, y, width, height)


class LuminaMainWindow(QMainWindow):
    """Lumina Qt 主窗口。"""

    WORKSPACE_NAMES = ["运行", "自定义操作序列", "坐标工具", "遮挡工具"]

    def __init__(self, *, runtime_controller: RuntimeController | None = None) -> None:
        super().__init__()
        self.runtime_controller = runtime_controller or AutomationRuntimeController()
        self.setWindowTitle("Lumina")
        self._apply_default_window_geometry()
        self._build_ui()

    def workspace_names(self) -> list[str]:
        return list(self.WORKSPACE_NAMES)

    def _apply_default_window_geometry(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1920, 1080)
            return
        available = screen.availableGeometry()
        dpr_scale = float(screen.devicePixelRatio() or 1.0)
        dpi_scale = float(screen.logicalDotsPerInch() or 96.0) / 96.0
        scale_factor = max(dpr_scale, dpi_scale, 1.0)
        x, y, width, height = compute_initial_window_geometry(
            available_x=available.x(),
            available_y=available.y(),
            available_width=available.width(),
            available_height=available.height(),
            scale_factor=scale_factor,
        )
        self.setGeometry(QRect(x, y, width, height))

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(12)
        title_label = QLabel("Lumina")
        title_label.setStyleSheet("font-size:16px;font-weight:600;")
        header_layout.addWidget(title_label)

        self.workspace_tabs = QTabBar()
        self.workspace_tabs.setDocumentMode(True)
        self.workspace_tabs.setDrawBase(False)
        self.workspace_tabs.setExpanding(False)
        self.workspace_tabs.setElideMode(Qt.TextElideMode.ElideNone)
        for name in self.WORKSPACE_NAMES:
            self.workspace_tabs.addTab(name)
        header_layout.addWidget(self.workspace_tabs)
        header_layout.addStretch(1)
        root.addWidget(header_frame, stretch=0)

        self.page_stack = QStackedWidget()
        page_container = QWidget()
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(14, 12, 14, 12)
        page_layout.setSpacing(0)
        page_layout.addWidget(self.page_stack, stretch=1)
        root.addWidget(page_container, stretch=1)

        self.runtime_page = RuntimePage(self.runtime_controller)
        self.custom_sequence_page = CustomSequencePage()
        self.coordinate_page = CoordinateToolPage()
        self.mask_region_page = MaskRegionToolPage()

        for page in (
            self.runtime_page,
            self.custom_sequence_page,
            self.coordinate_page,
            self.mask_region_page,
        ):
            self.page_stack.addWidget(page)

        self.workspace_tabs.currentChanged.connect(self.page_stack.setCurrentIndex)
        self.workspace_tabs.setCurrentIndex(0)
