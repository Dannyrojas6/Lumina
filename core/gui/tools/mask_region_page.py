"""Qt 版遮挡区域工具。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from scripts.mask_region_picker import (
    CropRect,
    MaskRect,
    apply_masks,
    crop_image,
    format_export_block,
)


TEST_IMAGE_DIR = Path(__file__).resolve().parents[3] / "test_image"


def qimage_to_rgb_array(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format.Format_RGB888)
    width = converted.width()
    height = converted.height()
    bytes_per_line = converted.bytesPerLine()
    ptr = converted.constBits()
    row_data = np.frombuffer(
        ptr,
        dtype=np.uint8,
        count=bytes_per_line * height,
    ).reshape(height, bytes_per_line)
    return row_data[:, : width * 3].reshape(height, width, 3).copy()


def rgb_array_to_qpixmap(image_rgb: np.ndarray) -> QPixmap:
    height, width, channels = image_rgb.shape
    image = QImage(
        image_rgb.data,
        width,
        height,
        channels * width,
        QImage.Format.Format_RGB888,
    ).copy()
    return QPixmap.fromImage(image)


class MaskCanvas(QWidget):
    crop_changed = Signal(str)
    mask_count_changed = Signal(str)
    export_changed = Signal(str)
    previews_changed = Signal(QPixmap, QPixmap)

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.image_path: Path | None = None
        self.image = QImage()
        self.scale = 1.0
        self.fit_scale = 1.0
        self.offset = QPointF(0, 0)
        self.crop_rect: tuple[int, int, int, int] | None = None
        self.mask_rects: list[tuple[int, int, int, int]] = []
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
        self.crop_rect = None
        self.mask_rects = []
        self.drag_origin = None
        self.drag_preview = None
        self.drag_mode = None
        self.scale = 1.0
        self._fit_image(reset_scale=True)
        self._emit_state()
        self.update()

    def clear_masks(self) -> None:
        self.mask_rects = []
        self._reset_drag_state()
        self._emit_state()
        self.update()

    def clear_all(self) -> None:
        self.crop_rect = None
        self.mask_rects = []
        self._reset_drag_state()
        self._emit_state()
        self.update()

    def remove_last_mask(self) -> None:
        if self.mask_rects:
            self.mask_rects.pop()
            self._emit_state()
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
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self.image.isNull():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_mode = "crop"
            self.drag_origin = self._widget_to_image(event.position().toPoint())
            self.drag_preview = self._normalize_rect(
                self.drag_origin[0],
                self.drag_origin[1],
                self.drag_origin[0],
                self.drag_origin[1],
            )
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.drag_mode = "mask"
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
        if self.drag_mode in {"crop", "mask"} and self.drag_origin is not None:
            current = self._widget_to_image(event.position().toPoint())
            raw_rect = self._normalize_rect(
                *self.drag_origin,
                current[0],
                current[1],
            )
            self.drag_preview = (
                self._clip_rect_to_crop(raw_rect)
                if self.drag_mode == "mask"
                else raw_rect
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

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        if self.drag_mode == "crop" and self.drag_preview is not None:
            self.crop_rect = self.drag_preview
            self.mask_rects = []
        elif (
            self.drag_mode == "mask"
            and self.drag_preview is not None
            and self.crop_rect is not None
        ):
            clipped = self._clip_rect_to_crop(self.drag_preview)
            if clipped is not None:
                self.mask_rects.append(clipped)
        self.drag_mode = None
        self.drag_origin = None
        self.drag_preview = None
        self.pan_anchor = None
        self.pan_offset_origin = None
        self._emit_state()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#141414"))
        if self.image.isNull():
            painter.setPen(QColor("#2a2a2a"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "选择图片后拖拽添加遮挡块")
            return
        target = QRectF(
            self.offset.x(),
            self.offset.y(),
            self.image.width() * self.scale,
            self.image.height() * self.scale,
        )
        painter.drawImage(target, self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.crop_rect is not None:
            self._draw_rect(painter, self.crop_rect, QColor("#59d38b"))
        for rect in self.mask_rects:
            clipped = self._clip_rect_to_crop(rect)
            if clipped is not None:
                self._draw_rect(painter, clipped, QColor("#f59f58"))
        if self.drag_preview is not None:
            color = QColor("#59d38b") if self.drag_mode == "crop" else QColor("#f7d24b")
            self._draw_rect(painter, self.drag_preview, color)

    def export_text(self) -> str:
        if self.image_path is None or self.crop_rect is None:
            return ""
        crop = CropRect(*self.crop_rect)
        masks = self._relative_masks()
        return format_export_block(self.image_path.name, crop, masks)

    def _emit_state(self) -> None:
        self.crop_changed.emit("-" if self.crop_rect is None else str(self.crop_rect))
        self.mask_count_changed.emit(str(len(self.mask_rects)))
        self.export_changed.emit(self.export_text())
        self._emit_previews()

    def _emit_previews(self) -> None:
        if self.image.isNull() or self.crop_rect is None:
            empty = QPixmap(220, 124)
            empty.fill(QColor("#121920"))
            self.previews_changed.emit(empty, empty)
            return
        image_rgb = qimage_to_rgb_array(self.image)
        crop = CropRect(*self.crop_rect)
        crop_rgb = crop_image(image_rgb, crop)
        masks = self._relative_masks()
        masked_rgb = apply_masks(crop_rgb, masks)
        self.previews_changed.emit(
            rgb_array_to_qpixmap(crop_rgb),
            rgb_array_to_qpixmap(masked_rgb),
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

    def _reset_drag_state(self) -> None:
        self.drag_origin = None
        self.drag_preview = None
        self.drag_mode = None
        self.pan_anchor = None
        self.pan_offset_origin = None

    def _clip_rect_to_crop(
        self,
        rect: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int] | None:
        if self.crop_rect is None:
            return None
        left = max(self.crop_rect[0], rect[0])
        top = max(self.crop_rect[1], rect[1])
        right = min(self.crop_rect[2], rect[2])
        bottom = min(self.crop_rect[3], rect[3])
        if right <= left or bottom <= top:
            return None
        return (left, top, right, bottom)

    def _relative_masks(self) -> list[MaskRect]:
        if self.crop_rect is None:
            return []
        crop = CropRect(*self.crop_rect)
        masks: list[MaskRect] = []
        for rect in self.mask_rects:
            clipped = self._clip_rect_to_crop(rect)
            if clipped is None:
                continue
            masks.append(
                MaskRect(
                    x1=clipped[0] - crop.x1,
                    y1=clipped[1] - crop.y1,
                    x2=clipped[2] - crop.x1,
                    y2=clipped[3] - crop.y1,
                )
            )
        return masks

    def _widget_to_image(self, point: QPoint) -> tuple[int, int]:
        float_point = self.widget_to_image_float(QPointF(point))
        x = min(max(int(float_point.x()), 0), self.image.width())
        y = min(max(int(float_point.y()), 0), self.image.height())
        return (x, y)

    def widget_to_image_float(self, point: QPointF) -> QPointF:
        return QPointF(
            (point.x() - self.offset.x()) / self.scale,
            (point.y() - self.offset.y()) / self.scale,
        )

    def _image_to_widget(self, point: tuple[int, int]) -> QPointF:
        return QPointF(
            self.offset.x() + point[0] * self.scale,
            self.offset.y() + point[1] * self.scale,
        )

    def _draw_rect(
        self,
        painter: QPainter,
        rect: tuple[int, int, int, int],
        color: QColor,
    ) -> None:
        painter.setPen(QPen(color, 2))
        top_left = self._image_to_widget((rect[0], rect[1]))
        bottom_right = self._image_to_widget((rect[2], rect[3]))
        painter.drawRect(QRectF(top_left, bottom_right))

    @staticmethod
    def _normalize_rect(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int, int]:
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


class MaskRegionToolPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def window_title(self) -> str:
        return "遮挡工具"

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar_frame = QFrame()
        toolbar_frame.setProperty("panelRole", "card")
        toolbar_frame.setProperty("layoutRole", "toolbar")
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(10, 7, 10, 7)
        toolbar_layout.setSpacing(5)
        open_button = QPushButton("选择图片")
        open_button.setObjectName("primaryButton")
        copy_export = QPushButton("复制导出文本")
        remove_last = QPushButton("撤销最后")
        remove_last.setObjectName("warningButton")
        clear_masks = QPushButton("清空遮挡")
        clear_masks.setObjectName("dangerButton")
        clear_all = QPushButton("清空全部")
        clear_all.setObjectName("dangerButton")
        for button in (open_button, copy_export, remove_last, clear_masks, clear_all):
            toolbar_layout.addWidget(button)
        toolbar_layout.addStretch(1)
        badge_label = QLabel("遮挡块")
        badge_label.setProperty("textRole", "muted")
        toolbar_layout.addWidget(badge_label)
        self.mask_count_badge = QLabel("0")
        self.mask_count_badge.setProperty("textRole", "badge")
        toolbar_layout.addWidget(self.mask_count_badge)
        root.addWidget(toolbar_frame, stretch=0)

        content_row = QHBoxLayout()
        content_row.setSpacing(10)
        root.addLayout(content_row, stretch=1)

        canvas_frame = QFrame()
        canvas_frame.setProperty("panelRole", "surface")
        canvas_frame.setProperty("layoutRole", "canvasPanel")
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(10, 10, 10, 10)
        canvas_layout.setSpacing(8)
        overlay_row = QHBoxLayout()
        overlay_row.setSpacing(6)
        crop_title = QLabel("裁剪区")
        crop_title.setProperty("textRole", "muted")
        overlay_row.addWidget(crop_title)
        self.crop_overlay_value = QLabel("—")
        self.crop_overlay_value.setProperty("textRole", "mono")
        overlay_row.addWidget(self.crop_overlay_value)
        overlay_row.addStretch(1)
        canvas_layout.addLayout(overlay_row)
        self.canvas = MaskCanvas()
        self.canvas.setObjectName("maskToolCanvas")
        self.canvas.setMinimumHeight(440)
        canvas_layout.addWidget(self.canvas, stretch=1)
        content_row.addWidget(canvas_frame, stretch=1)

        side_panel = QFrame()
        side_panel.setObjectName("maskToolSidePanel")
        side_panel.setProperty("panelRole", "card")
        side_panel.setProperty("layoutRole", "sidePanel")
        side_panel.setFixedWidth(210)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(10, 10, 10, 10)
        side_layout.setSpacing(10)

        self.crop_label = self._value_label("裁剪区：-")
        self.mask_count_label = self._value_label("遮挡块数量：0")
        side_layout.addWidget(self.crop_label)
        side_layout.addWidget(self.mask_count_label)

        side_layout.addWidget(self._section_label("裁剪预览"))
        self.crop_preview = QLabel()
        self.crop_preview.setProperty("previewRole", "toolPreview")
        self.crop_preview.setFixedHeight(96)
        self.crop_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        side_layout.addWidget(self.crop_preview)

        side_layout.addWidget(self._section_label("遮挡预览"))
        self.mask_preview = QLabel()
        self.mask_preview.setProperty("previewRole", "toolPreview")
        self.mask_preview.setFixedHeight(96)
        self.mask_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mask_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        side_layout.addWidget(self.mask_preview)

        side_layout.addWidget(self._section_label("导出文本"))
        self.export_edit = QTextEdit()
        self.export_edit.setProperty("editorRole", "export")
        self.export_edit.setMinimumHeight(160)
        side_layout.addWidget(self.export_edit, stretch=1)
        content_row.addWidget(side_panel, stretch=0)

        open_button.clicked.connect(self._choose_image)
        copy_export.clicked.connect(
            lambda: QApplication.clipboard().setText(self.export_edit.toPlainText())
        )
        remove_last.clicked.connect(self.canvas.remove_last_mask)
        clear_masks.clicked.connect(self.canvas.clear_masks)
        clear_all.clicked.connect(self.canvas.clear_all)
        self.canvas.crop_changed.connect(self._on_crop_changed)
        self.canvas.mask_count_changed.connect(self._on_mask_count_changed)
        self.canvas.export_changed.connect(self.export_edit.setPlainText)
        self.canvas.previews_changed.connect(self._set_previews)

    def _choose_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择测试图片",
            str(TEST_IMAGE_DIR),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not file_path:
            return
        self.canvas.set_image(Path(file_path))

    def _set_previews(self, crop: QPixmap, masked: QPixmap) -> None:
        self.crop_preview.setPixmap(
            crop.scaled(
                self.crop_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.mask_preview.setPixmap(
            masked.scaled(
                self.mask_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _on_crop_changed(self, text: str) -> None:
        self.crop_label.setText(f"裁剪区：{text}")
        self.crop_overlay_value.setText(text)

    def _on_mask_count_changed(self, text: str) -> None:
        self.mask_count_label.setText(f"遮挡块数量：{text}")
        self.mask_count_badge.setText(text)

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("textRole", "section")
        return label

    def _value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setProperty("textRole", "muted")
        return label
