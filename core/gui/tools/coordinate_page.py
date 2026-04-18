"""Qt 版坐标拾取工具。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


TEST_IMAGE_DIR = Path(__file__).resolve().parents[3] / "test_image"


class CoordinateCanvas(QWidget):
    cursor_changed = Signal(str)
    point_changed = Signal(str)
    rect_changed = Signal(str)
    scale_changed = Signal(str)

    CROSSHAIR_HALF_SIZE = 8

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.image_path: Path | None = None
        self.image = QImage()
        self.scale = 1.0
        self.fit_scale = 1.0
        self.offset = QPointF(0, 0)
        self.latest_point: tuple[int, int] | None = None
        self.latest_rect: tuple[int, int, int, int] | None = None
        self.drag_origin: tuple[int, int] | None = None
        self.drag_preview: tuple[int, int, int, int] | None = None
        self.drag_mode: str | None = None
        self.pan_anchor: QPoint | None = None
        self.pan_offset_origin: QPointF | None = None

    def set_image(self, path: Path) -> None:
        image = QImage(str(path))
        if image.isNull():
            return
        self.image_path = path
        self.set_qimage(image)

    def set_qimage(self, image: QImage) -> None:
        if image.isNull():
            return
        self.image = image
        self.scale = 1.0
        self.latest_point = None
        self.latest_rect = None
        self.drag_preview = None
        self._fit_image(reset_scale=True)
        self._emit_all()
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self.image.isNull():
            self._fit_image(reset_scale=False)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self.image.isNull():
            return
        factor = 1.1 if event.angleDelta().y() > 0 else 1 / 1.1
        self.zoom_at(event.position(), factor)

    def zoom_at(self, widget_pos: QPointF, factor: float) -> None:
        if self.image.isNull():
            return
        old_pos = self.widget_to_image_float(widget_pos)
        self.scale = min(max(self.scale * factor, self.fit_scale), 8.0)
        self.offset = QPointF(
            widget_pos.x() - old_pos.x() * self.scale,
            widget_pos.y() - old_pos.y() * self.scale,
        )
        self.scale_changed.emit(f"{self.scale:.2f}x")
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self.image.isNull():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_mode = "point"
            self.latest_point = self._widget_to_image(event.position().toPoint())
            self.point_changed.emit(str(self.latest_point))
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.drag_mode = "rect"
            self.drag_origin = self._widget_to_image(event.position().toPoint())
            self.drag_preview = self._normalize_rect(
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
            )
            self.update()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.drag_mode = "pan"
            self.pan_anchor = event.position().toPoint()
            self.pan_offset_origin = QPointF(self.offset)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.image.isNull():
            return
        image_point = self._widget_to_image(event.position().toPoint())
        self.cursor_changed.emit(str(image_point))
        if self.drag_mode == "rect" and self.drag_origin is not None:
            self.drag_preview = self._normalize_rect(
                *self.drag_origin,
                image_point[0],
                image_point[1],
            )
            self.update()
        elif (
            self.drag_mode == "pan"
            and self.pan_anchor is not None
            and self.pan_offset_origin is not None
        ):
            delta = event.position().toPoint() - self.pan_anchor
            self.offset = QPointF(
                self.pan_offset_origin.x() + delta.x(),
                self.pan_offset_origin.y() + delta.y(),
            )
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton and self.drag_preview is not None:
            self.latest_rect = self.drag_preview
            self.rect_changed.emit(str(self.latest_rect))
        self.drag_mode = None
        self.drag_origin = None
        self.drag_preview = None
        self.pan_anchor = None
        self.pan_offset_origin = None
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0b1015"))
        if self.image.isNull():
            return
        target = QRectF(
            self.offset.x(),
            self.offset.y(),
            self.image.width() * self.scale,
            self.image.height() * self.scale,
        )
        painter.drawImage(target, self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.latest_point is not None:
            horizontal, vertical = self.crosshair_segments(self.latest_point)
            painter.setPen(QPen(QColor("#f7d24b"), 2))
            painter.drawLine(
                QPointF(*horizontal[0]),
                QPointF(*horizontal[1]),
            )
            painter.drawLine(
                QPointF(*vertical[0]),
                QPointF(*vertical[1]),
            )
        rect_to_draw = self.active_rect_to_draw()
        if rect_to_draw is not None:
            x1, y1, x2, y2 = rect_to_draw
            painter.setPen(QPen(QColor("#59d38b"), 2))
            top_left = self._image_to_widget((x1, y1))
            bottom_right = self._image_to_widget((x2, y2))
            painter.drawRect(QRectF(top_left, bottom_right))

    def active_rect_to_draw(self) -> tuple[int, int, int, int] | None:
        return self.drag_preview if self.drag_preview is not None else self.latest_rect

    def crosshair_segments(
        self,
        point: tuple[int, int],
    ) -> tuple[tuple[tuple[float, float], tuple[float, float]], tuple[tuple[float, float], tuple[float, float]]]:
        widget_point = self._image_to_widget(point)
        return (
            (
                (widget_point.x() - self.CROSSHAIR_HALF_SIZE, widget_point.y()),
                (widget_point.x() + self.CROSSHAIR_HALF_SIZE, widget_point.y()),
            ),
            (
                (widget_point.x(), widget_point.y() - self.CROSSHAIR_HALF_SIZE),
                (widget_point.x(), widget_point.y() + self.CROSSHAIR_HALF_SIZE),
            ),
        )

    def _fit_image(self, *, reset_scale: bool) -> None:
        if self.image.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        self.fit_scale = min(
            self.width() / self.image.width(),
            self.height() / self.image.height(),
        )
        self.scale = self.fit_scale if reset_scale else max(self.scale, self.fit_scale)
        width = self.image.width() * self.scale
        height = self.image.height() * self.scale
        self.offset = QPointF((self.width() - width) / 2, (self.height() - height) / 2)
        self.scale_changed.emit(f"{self.scale:.2f}x")

    def _emit_all(self) -> None:
        self.cursor_changed.emit("-")
        self.point_changed.emit("-")
        self.rect_changed.emit("-")
        self.scale_changed.emit(f"{self.scale:.2f}x")

    def _widget_to_image(self, point: QPoint) -> tuple[int, int]:
        if self.image.isNull():
            return (0, 0)
        float_point = self.widget_to_image_float(QPointF(point))
        x = min(max(int(float_point.x()), 0), self.image.width())
        y = min(max(int(float_point.y()), 0), self.image.height())
        return (x, y)

    def widget_to_image_float(self, point: QPointF) -> QPointF:
        if self.image.isNull():
            return QPointF(0, 0)
        return QPointF(
            (point.x() - self.offset.x()) / self.scale,
            (point.y() - self.offset.y()) / self.scale,
        )

    def _image_to_widget(self, point: tuple[int, int]) -> QPointF:
        return QPointF(
            self.offset.x() + point[0] * self.scale,
            self.offset.y() + point[1] * self.scale,
        )

    @staticmethod
    def _normalize_rect(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int, int]:
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


class CoordinateToolPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def window_title(self) -> str:
        return "坐标工具"

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        open_button = QPushButton("选择图片")
        toolbar.addWidget(open_button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        content_row = QHBoxLayout()
        content_row.setSpacing(10)
        root.addLayout(content_row, stretch=1)

        self.canvas = CoordinateCanvas()
        content_row.addWidget(self.canvas, stretch=1)

        info_frame = QFrame()
        info_frame.setObjectName("coordinateToolSidePanel")
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setMaximumWidth(360)
        info_frame.setMinimumWidth(300)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(10)

        self.file_label = QLabel("文件：未选择")
        self.scale_label = QLabel("倍率：-")
        self.cursor_label = QLabel("当前坐标：-")
        self.point_label = QLabel("最新点：-")
        self.rect_label = QLabel("最新矩形：-")
        labels = [
            self.file_label,
            self.scale_label,
            self.cursor_label,
            self.point_label,
            self.rect_label,
        ]
        for label in labels:
            label.setWordWrap(True)

        info_layout.addWidget(self.file_label)
        info_layout.addWidget(self.scale_label)
        info_layout.addWidget(self.cursor_label)
        info_layout.addWidget(self.point_label)
        info_layout.addWidget(self.rect_label)

        self.copy_point_button = QPushButton("复制点坐标")
        self.copy_rect_button = QPushButton("复制矩形坐标")
        info_layout.addWidget(self.copy_point_button)
        info_layout.addWidget(self.copy_rect_button)
        info_layout.addStretch(1)
        content_row.addWidget(info_frame, stretch=0)

        open_button.clicked.connect(self._choose_image)
        self.copy_point_button.clicked.connect(
            lambda: QApplication.clipboard().setText(
                self.point_label.text().split("：", 1)[-1]
            )
        )
        self.copy_rect_button.clicked.connect(
            lambda: QApplication.clipboard().setText(
                self.rect_label.text().split("：", 1)[-1]
            )
        )
        self.canvas.cursor_changed.connect(
            lambda text: self.cursor_label.setText(f"当前坐标：{text}")
        )
        self.canvas.point_changed.connect(
            lambda text: self.point_label.setText(f"最新点：{text}")
        )
        self.canvas.rect_changed.connect(
            lambda text: self.rect_label.setText(f"最新矩形：{text}")
        )
        self.canvas.scale_changed.connect(
            lambda text: self.scale_label.setText(f"倍率：{text}")
        )

    def _choose_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择测试图片",
            str(TEST_IMAGE_DIR),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not file_path:
            return
        path = Path(file_path)
        self.file_label.setText(f"文件：{path}")
        self.canvas.set_image(path)
