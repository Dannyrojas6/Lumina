"""主运行工作区页面。"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.gui.runtime.controller import RuntimeController
from core.gui.services.runtime_config_service import RuntimeEditableConfig


class _RuntimeToggleSwitch(QAbstractButton):
    """运行页使用的滑动开关。"""

    def __init__(self) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(54, 28)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(54, 28)

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(54, 28)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        checked = self.isChecked()
        enabled = self.isEnabled()
        track_rect = QRectF(0, 2, 50, 24)
        knob_diameter = 18
        knob_margin = 3

        track_color = QColor("#26c281" if checked else "#34383e")
        text_color = QColor("#26c281" if checked else "#7a7f87")
        knob_color = QColor("#f5f7fa" if enabled else "#c0c5cb")

        if not enabled:
            track_color.setAlpha(130)
            text_color.setAlpha(120)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, 12, 12)

        knob_x = (
            track_rect.right() - knob_diameter - knob_margin
            if checked
            else track_rect.left() + knob_margin
        )
        knob_rect = QRectF(
            knob_x,
            track_rect.top() + 3,
            knob_diameter,
            knob_diameter,
        )
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_rect)


class _RuntimeComboBox(QComboBox):
    """运行页使用的深色下拉框。"""

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("controlRole", "formCombo")
        self.setFixedHeight(28)

    def showPopup(self) -> None:  # type: ignore[override]
        view = self.view()
        if view is not None and self.model() is not None:
            metrics = view.fontMetrics()
            width = self.width()
            for index in range(self.count()):
                text = self.itemText(index)
                width = max(width, metrics.horizontalAdvance(text) + 36)
            view.setMinimumWidth(width)
        super().showPopup()


class RuntimePage(QWidget):
    """运行页，负责开始/停止、摘要、状态和截图预览。"""

    SIDE_COLUMN_MIN_WIDTH = 150
    COLUMN_GAP = 6
    CENTER_PANEL_GAP = 6
    MODE_COMBO_MIN_WIDTH = 138
    MODE_COMBO_MAX_WIDTH = 138
    LOG_LEVEL_COMBO_MIN_WIDTH = 138
    LOG_LEVEL_COMBO_MAX_WIDTH = 138
    COMBO_TEXT_PADDING = 28
    PREVIEW_HEADER_HEIGHT = 38
    LOG_HEADER_HEIGHT = 34
    DEFAULT_PREVIEW_TOTAL_HEIGHT = 405
    DEFAULT_LOG_TOTAL_HEIGHT = 190

    class _AspectRatioPreview(QWidget):
        """固定按 16:9 绘制截图预览。"""

        ASPECT_WIDTH = 16
        ASPECT_HEIGHT = 9

        def __init__(self, preferred_size: QSize, minimum_hint: QSize) -> None:
            super().__init__()
            self._preferred_size = QSize(preferred_size)
            self._minimum_hint = QSize(minimum_hint)
            self._image = QImage()
            self._placeholder_text = "等待画面"
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self.setMinimumSize(minimum_hint)
            self.setObjectName("runtimePreviewViewport")

        def hasHeightForWidth(self) -> bool:  # type: ignore[override]
            return True

        def heightForWidth(self, width: int) -> int:  # type: ignore[override]
            if width <= 0:
                return self._minimum_hint.height()
            return int(round(width * self.ASPECT_HEIGHT / self.ASPECT_WIDTH))

        def sizeHint(self) -> QSize:  # type: ignore[override]
            return QSize(self._preferred_size)

        def minimumSizeHint(self) -> QSize:  # type: ignore[override]
            return QSize(self._minimum_hint)

        def set_image(self, image: QImage) -> None:
            self._image = QImage(image)
            self.update()

        def paintEvent(self, _event) -> None:  # type: ignore[override]
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            target_rect = self._aspect_rect(self.contentsRect())
            if self._image.isNull():
                painter.setPen(QColor("#5f646b"))
                painter.drawText(
                    target_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    self._placeholder_text,
                )
                return

            pixmap = QPixmap.fromImage(self._image).scaled(
                target_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            origin_x = target_rect.x() + max((target_rect.width() - pixmap.width()) // 2, 0)
            origin_y = target_rect.y() + max((target_rect.height() - pixmap.height()) // 2, 0)
            painter.drawPixmap(origin_x, origin_y, pixmap)

        def _aspect_rect(self, rect: QRect) -> QRect:
            if rect.width() <= 0 or rect.height() <= 0:
                return rect

            width = rect.width()
            height = self.heightForWidth(width)
            if height > rect.height():
                height = rect.height()
                width = int(round(height * self.ASPECT_WIDTH / self.ASPECT_HEIGHT))

            x = rect.x() + max((rect.width() - width) // 2, 0)
            y = rect.y() + max((rect.height() - height) // 2, 0)
            return QRect(x, y, width, height)

    def __init__(
        self,
        runtime_controller: RuntimeController,
    ) -> None:
        super().__init__()
        self.runtime_controller = runtime_controller
        self._summary_text = getattr(runtime_controller, "current_summary", "") or "等待读取配置"
        self._config_available = bool(
            getattr(runtime_controller, "config_available", True)
        )
        self._saved_config = runtime_controller.load_editable_config()
        self._suppress_config_signals = False
        self._is_running = False
        self._status_text = "空闲"
        self._log_dialog: QDialog | None = None
        self._log_dialog_output: QTextEdit | None = None
        self._updating_right_layout = False
        self._build_ui()
        self._bind_controller()
        self._load_config_controls(self._saved_config)
        self._apply_summary(self._summary_text)
        self._sync_controller_config_state(force=True)
        self.set_status_text(self._controller_lifecycle_text())

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(self.COLUMN_GAP)

        self.settings_column = self._make_card(
            "runtimeSettingsColumn",
            layout_role="sidePanel",
        )
        self.settings_column.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        settings_layout = QVBoxLayout(self.settings_column)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        settings_layout.setSpacing(10)

        self.action_buttons_row = QWidget()
        action_buttons_layout = QHBoxLayout(self.action_buttons_row)
        action_buttons_layout.setContentsMargins(0, 2, 0, 2)
        action_buttons_layout.setSpacing(6)

        self.start_button = QPushButton("▶ 开始")
        self.start_button.setObjectName("successButton")
        self.start_button.setFixedHeight(30)
        action_buttons_layout.addWidget(self.start_button, stretch=1)

        self.stop_button = QPushButton("■ 停止")
        self.stop_button.setEnabled(False)
        self.stop_button.setFixedHeight(30)
        action_buttons_layout.addWidget(self.stop_button, stretch=1)
        settings_layout.addWidget(self.action_buttons_row)

        self.config_card = self._make_card()
        config_layout = QVBoxLayout(self.config_card)
        config_layout.setContentsMargins(10, 8, 10, 8)
        config_layout.setSpacing(7)
        config_layout.addWidget(self._section_label("运行前配置"))

        self.mode_combo = _RuntimeComboBox()
        self.mode_combo.addItems(["main", "custom_sequence"])
        self.mode_combo.setView(self._create_combo_view())
        self.smart_battle_checkbox = _RuntimeToggleSwitch()
        self.continue_battle_checkbox = _RuntimeToggleSwitch()
        self.log_level_combo = _RuntimeComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING"])
        self.log_level_combo.setView(self._create_combo_view())

        config_grid = QGridLayout()
        config_grid.setHorizontalSpacing(8)
        config_grid.setVerticalSpacing(7)
        config_grid.addWidget(self._muted_label("模式"), 0, 0)
        config_grid.addWidget(self.mode_combo, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        config_grid.addWidget(self._muted_label("智能战斗"), 1, 0)
        config_grid.addWidget(self.smart_battle_checkbox, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        config_grid.addWidget(self._muted_label("连续出击"), 2, 0)
        config_grid.addWidget(self.continue_battle_checkbox, 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
        config_grid.addWidget(self._muted_label("日志级别"), 3, 0)
        config_grid.addWidget(self.log_level_combo, 3, 1, alignment=Qt.AlignmentFlag.AlignRight)
        config_layout.addLayout(config_grid)

        config_buttons = QHBoxLayout()
        config_buttons.setSpacing(6)
        self.apply_button = QPushButton("应用")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.setFixedHeight(30)
        self.reset_button = QPushButton("恢复")
        self.reset_button.setFixedHeight(30)
        config_buttons.addWidget(self.apply_button, stretch=1)
        config_buttons.addWidget(self.reset_button, stretch=1)
        config_layout.addLayout(config_buttons)

        self.config_status_label = QLabel()
        self._set_config_status_saved()
        config_layout.addWidget(self.config_status_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        settings_layout.addWidget(self.config_card)
        settings_layout.addStretch(1)
        root.addWidget(self.settings_column, stretch=0)

        self.center_stage = QWidget()
        self.center_stage.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        center_layout = QVBoxLayout(self.center_stage)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(self.CENTER_PANEL_GAP)

        self.preview_card = self._make_surface(layout_role="canvasPanel")
        self.preview_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        self.preview_head_widget = QWidget()
        self.preview_head_widget.setProperty("headerRole", "panel")
        self.preview_head_widget.setFixedHeight(self.PREVIEW_HEADER_HEIGHT)
        preview_head = QHBoxLayout(self.preview_head_widget)
        preview_head.setContentsMargins(10, 5, 10, 5)
        self.preview_title_label = QLabel("实时画面")
        self.preview_title_label.setProperty("textRole", "panelTitle")
        preview_head.addWidget(self.preview_title_label)
        preview_head.addStretch(1)
        self.preview_status_value = QLabel("空闲")
        self.preview_status_value.setObjectName("runtimePreviewStatusValue")
        self.preview_status_value.setProperty("statusState", "idle")
        self.preview_status_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_status_value.setFixedHeight(26)
        self.preview_status_value.setMinimumWidth(62)
        preview_head.addWidget(self.preview_status_value)
        preview_layout.addWidget(self.preview_head_widget)
        self.preview_label = self._AspectRatioPreview(
            preferred_size=QSize(720, 405),
            minimum_hint=QSize(560, 315),
        )
        preview_layout.addWidget(self.preview_label, stretch=1)

        self.log_card = self._make_surface(layout_role="canvasPanel")
        self.log_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)
        self.log_head_widget = QWidget()
        self.log_head_widget.setProperty("headerRole", "panel")
        self.log_head_widget.setFixedHeight(self.LOG_HEADER_HEIGHT)
        log_head = QHBoxLayout(self.log_head_widget)
        log_head.setContentsMargins(10, 4, 10, 4)
        self.log_title_label = QLabel("运行日志")
        self.log_title_label.setProperty("textRole", "panelTitle")
        log_head.addWidget(self.log_title_label)
        log_head.addStretch(1)
        self.log_clear_button = QPushButton("清空")
        self.log_clear_button.setProperty("buttonRole", "headerAction")
        self.log_clear_button.setFixedWidth(54)
        self.log_clear_button.setFixedHeight(26)
        self.log_popout_button = QPushButton("全屏")
        self.log_popout_button.setProperty("buttonRole", "headerAction")
        self.log_popout_button.setFixedWidth(54)
        self.log_popout_button.setFixedHeight(26)
        log_head.addWidget(self.log_clear_button)
        log_head.addWidget(self.log_popout_button)
        log_layout.addWidget(self.log_head_widget)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("runtimeLogOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(140)
        log_layout.addWidget(self.log_output)

        center_layout.addWidget(self.preview_card)
        center_layout.addWidget(self.log_card)
        root.addWidget(self.center_stage, stretch=0)

        self.summary_column = self._make_card(
            "runtimeSummaryColumn",
            layout_role="sidePanel",
        )
        self.summary_column.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        summary_column_layout = QVBoxLayout(self.summary_column)
        summary_column_layout.setContentsMargins(10, 10, 10, 10)
        summary_column_layout.setSpacing(10)

        self.summary_card = self._make_card()
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(6)
        self.summary_section_label = self._section_label("当前已保存配置")
        summary_layout.addWidget(self.summary_section_label)
        self.mode_value = QLabel("-")
        self.smart_value = QLabel("-")
        self.continue_value = QLabel("-")
        self.log_level_value = QLabel("-")
        self.support_value = QLabel("-")
        self.sequence_value = QLabel("-")
        self.support_value.setWordWrap(False)
        self.sequence_value.setWordWrap(False)
        self.support_value.setMaximumWidth(180)
        self.sequence_value.setMaximumWidth(180)
        self.support_value.setTextFormat(Qt.TextFormat.PlainText)
        self.sequence_value.setTextFormat(Qt.TextFormat.PlainText)
        for key, value in (
            ("模式", self.mode_value),
            ("智能战斗", self.smart_value),
            ("连续出击", self.continue_value),
            ("日志级别", self.log_level_value),
            ("助战目标", self.support_value),
            ("操作序列", self.sequence_value),
        ):
            summary_layout.addLayout(self._kv_row(key, value))
        summary_column_layout.addWidget(self.summary_card)
        summary_column_layout.addStretch(1)
        root.addWidget(self.summary_column, stretch=0)

        self.setMinimumWidth(
            self.preview_label.minimumSizeHint().width()
            + self.SIDE_COLUMN_MIN_WIDTH * 2
            + self.layout().spacing() * 2
        )

        self.start_button.clicked.connect(self._handle_start_clicked)
        self.stop_button.clicked.connect(self._handle_stop_clicked)
        self.log_clear_button.clicked.connect(self.log_output.clear)
        self.log_popout_button.clicked.connect(self._show_log_dialog)
        self.mode_combo.currentTextChanged.connect(self._on_config_value_changed)
        self.smart_battle_checkbox.toggled.connect(self._on_config_value_changed)
        self.continue_battle_checkbox.toggled.connect(self._on_config_value_changed)
        self.log_level_combo.currentTextChanged.connect(self._on_config_value_changed)
        self.apply_button.clicked.connect(self._handle_apply_clicked)
        self.reset_button.clicked.connect(self._handle_reset_clicked)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._update_right_layout()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_right_layout()

    def _bind_controller(self) -> None:
        self.runtime_controller.lifecycle_changed.connect(self.set_status_text)
        self.runtime_controller.preview_changed.connect(self.set_preview_image)
        self.runtime_controller.running_changed.connect(self.set_running_state)
        self.runtime_controller.summary_changed.connect(self.set_summary_text)
        self.runtime_controller.log_emitted.connect(self.append_log)

    def set_running_state(self, is_running: bool) -> None:
        self._is_running = is_running
        self._sync_controller_config_state()
        self._refresh_action_buttons()
        self._refresh_config_controls_enabled()

    def set_status_text(self, text: str) -> None:
        self._sync_controller_config_state()
        self._status_text = text
        self.preview_status_value.setText(text)
        self._update_lifecycle_visuals(text)
        self._refresh_action_buttons()
        self._refresh_config_controls_enabled()

    def set_summary_text(self, summary: str) -> None:
        self._summary_text = summary
        self._apply_summary(summary)

    def set_preview_image(self, image: QImage) -> None:
        self.preview_label.set_image(image)

    def _handle_start_clicked(self) -> None:
        if not self.start_button.isEnabled():
            return
        self.set_status_text("启动中")
        self.runtime_controller.start()

    def _handle_stop_clicked(self) -> None:
        self.runtime_controller.stop()

    def _handle_apply_clicked(self) -> None:
        if not self._controller_config_available():
            return
        config = self._build_current_config()
        self.runtime_controller.apply_editable_config(config)
        self._saved_config = config
        self._load_config_controls(config)
        self._set_config_status_saved()
        self._refresh_config_controls_enabled()

    def _handle_reset_clicked(self) -> None:
        if not self._controller_config_available():
            return
        self._saved_config = self.runtime_controller.load_editable_config()
        self._load_config_controls(self._saved_config)
        self._set_config_status_saved()
        self._refresh_config_controls_enabled()

    def append_log(self, message: str) -> None:
        self.log_output.append(message)
        if self._log_dialog_output is not None:
            self._log_dialog_output.append(message)

    def _show_log_dialog(self) -> None:
        if self._log_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("运行日志")
            dialog.resize(980, 640)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(10, 10, 10, 10)
            output = QTextEdit()
            output.setReadOnly(True)
            output.setPlainText(self.log_output.toPlainText())
            layout.addWidget(output)
            self._log_dialog = dialog
            self._log_dialog_output = output
        else:
            self._log_dialog_output.setPlainText(self.log_output.toPlainText())
        self._log_dialog.show()
        self._log_dialog.raise_()
        self._log_dialog.activateWindow()

    def _apply_summary(self, summary: str) -> None:
        values = {}
        for line in summary.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        self.mode_value.setText(values.get("battle_mode", "-"))
        self.smart_value.setText(values.get("smart_battle", "-"))
        self.continue_value.setText(values.get("continue_battle", "-"))
        self.log_level_value.setText(values.get("log_level", "-"))
        self._set_summary_value(self.support_value, values.get("support", "-"))
        self._set_summary_value(self.sequence_value, values.get("custom_sequence", "-"))

    def _load_config_controls(self, config: RuntimeEditableConfig) -> None:
        self._suppress_config_signals = True
        self.mode_combo.setCurrentText(config.battle_mode)
        self.smart_battle_checkbox.setChecked(config.smart_battle_enabled)
        self.continue_battle_checkbox.setChecked(config.continue_battle)
        self.log_level_combo.setCurrentText(config.log_level)
        self._suppress_config_signals = False
        self._update_runtime_form_widths()
        self._sync_mode_controls()

    def _build_current_config(self) -> RuntimeEditableConfig:
        return RuntimeEditableConfig(
            battle_mode=self.mode_combo.currentText(),  # type: ignore[arg-type]
            smart_battle_enabled=self.smart_battle_checkbox.isChecked(),
            continue_battle=self.continue_battle_checkbox.isChecked(),
            log_level=self.log_level_combo.currentText(),  # type: ignore[arg-type]
        )

    def _on_config_value_changed(self, *_args) -> None:
        if self._suppress_config_signals:
            return
        self._update_runtime_form_widths()
        self._sync_mode_controls()
        if self._build_current_config() == self._saved_config:
            self._set_config_status_saved()
        else:
            self._set_config_status_dirty()
        self._refresh_config_controls_enabled()

    def _update_runtime_form_widths(self) -> None:
        self._set_combo_fixed_width(
            self.mode_combo,
            text=self.mode_combo.currentText(),
            min_width=self.MODE_COMBO_MIN_WIDTH,
            max_width=self.MODE_COMBO_MAX_WIDTH,
        )
        self._set_combo_fixed_width(
            self.log_level_combo,
            text=self.log_level_combo.currentText(),
            min_width=self.LOG_LEVEL_COMBO_MIN_WIDTH,
            max_width=self.LOG_LEVEL_COMBO_MAX_WIDTH,
        )

    def _set_combo_fixed_width(
        self,
        combo: QComboBox,
        *,
        text: str,
        min_width: int,
        max_width: int,
    ) -> None:
        text_width = combo.fontMetrics().horizontalAdvance(text or "")
        target_width = max(text_width + self.COMBO_TEXT_PADDING, min_width)
        combo.setFixedWidth(min(target_width, max_width))
        combo.setToolTip(text)

    def _sync_mode_controls(self) -> None:
        self.smart_battle_checkbox.setEnabled(
            self.mode_combo.currentText() == "main" and self._controls_editable()
        )

    def _controls_editable(self) -> bool:
        return (
            self._controller_config_available()
            and not self._is_running
            and self._status_text not in {"启动中", "停止中"}
        )

    def _refresh_config_controls_enabled(self) -> None:
        if not self._controller_config_available():
            self.mode_combo.setEnabled(False)
            self.smart_battle_checkbox.setEnabled(False)
            self.continue_battle_checkbox.setEnabled(False)
            self.log_level_combo.setEnabled(False)
            self.apply_button.setEnabled(False)
            self.reset_button.setEnabled(False)
            self._set_config_status_unavailable()
            return
        editable = self._controls_editable()
        self.mode_combo.setEnabled(editable)
        self.continue_battle_checkbox.setEnabled(editable)
        self.log_level_combo.setEnabled(editable)
        self._sync_mode_controls()
        dirty = self._build_current_config() != self._saved_config
        self.apply_button.setEnabled(editable and dirty)
        self.reset_button.setEnabled(editable and dirty)

    def _refresh_action_buttons(self) -> None:
        status_text = self._status_text
        can_start = (
            self._controller_config_available()
            and not self._is_running
            and status_text not in {"启动中", "停止中"}
        )
        can_stop = (
            self._controller_config_available()
            and self._is_running
            and status_text not in {"启动中", "停止中"}
        )
        self.start_button.setEnabled(can_start)
        self.stop_button.setEnabled(can_stop)

    def _controller_config_available(self) -> bool:
        return bool(getattr(self.runtime_controller, "config_available", True))

    def _controller_lifecycle_text(self) -> str:
        return getattr(self.runtime_controller, "current_lifecycle_text", "空闲") or "空闲"

    def _controller_config_error_text(self) -> str:
        return getattr(self.runtime_controller, "current_config_error", None) or "配置不可用"

    def _sync_controller_config_state(self, *, force: bool = False) -> None:
        available = self._controller_config_available()
        if force or available != self._config_available:
            self._saved_config = self.runtime_controller.load_editable_config()
            available = self._controller_config_available()
            self._config_available = available
            self._load_config_controls(self._saved_config)
            if available:
                self._set_config_status_saved()
            else:
                self._set_config_status_unavailable()
        elif not available:
            self._set_config_status_unavailable()

    def _update_right_layout(self) -> None:
        if self._updating_right_layout:
            return
        self._updating_right_layout = True
        try:
            layout = self.layout()
            if not isinstance(layout, QHBoxLayout):
                return

            available_width = max(self.contentsRect().width(), 0)
            min_side_total = self.SIDE_COLUMN_MIN_WIDTH * 2
            available_center_width = max(
                available_width - min_side_total - layout.spacing() * 2,
                self.preview_label.minimumSizeHint().width(),
            )

            preview_header_height = self.preview_head_widget.height()
            min_preview_total = (
                preview_header_height + self.preview_label.minimumSizeHint().height()
            )
            min_log_total = self.log_head_widget.height() + self.log_output.minimumHeight()
            total_center_height = max(
                self.contentsRect().height(),
                min_preview_total + self.CENTER_PANEL_GAP + min_log_total,
            )

            preview_ratio = self.DEFAULT_PREVIEW_TOTAL_HEIGHT / (
                self.DEFAULT_PREVIEW_TOTAL_HEIGHT + self.DEFAULT_LOG_TOTAL_HEIGHT
            )
            desired_preview_total = int(
                round((total_center_height - self.CENTER_PANEL_GAP) * preview_ratio)
            )
            max_preview_total = max(
                total_center_height - self.CENTER_PANEL_GAP - min_log_total,
                min_preview_total,
            )
            desired_preview_total = min(
                max(desired_preview_total, min_preview_total),
                max_preview_total,
            )
            desired_preview_body_height = max(
                desired_preview_total - preview_header_height,
                self.preview_label.minimumSizeHint().height(),
            )
            desired_center_width = int(round(desired_preview_body_height * 16 / 9))
            final_center_width = max(
                self.preview_label.minimumSizeHint().width(),
                min(desired_center_width, available_center_width),
            )

            final_preview_body_height = int(round(final_center_width * 9 / 16))
            final_preview_total = preview_header_height + final_preview_body_height
            final_log_total = total_center_height - self.CENTER_PANEL_GAP - final_preview_total
            if final_log_total < min_log_total:
                final_log_total = min_log_total
                final_preview_total = (
                    total_center_height - self.CENTER_PANEL_GAP - final_log_total
                )
                final_preview_body_height = max(
                    final_preview_total - preview_header_height,
                    self.preview_label.minimumSizeHint().height(),
                )
                final_center_width = max(
                    self.preview_label.minimumSizeHint().width(),
                    min(int(round(final_preview_body_height * 16 / 9)), available_center_width),
                )
                final_preview_body_height = int(round(final_center_width * 9 / 16))
                final_preview_total = preview_header_height + final_preview_body_height
                final_log_total = total_center_height - self.CENTER_PANEL_GAP - final_preview_total

            side_total_width = max(
                available_width - final_center_width - layout.spacing() * 2,
                min_side_total,
            )
            left_width = side_total_width // 2
            right_width = side_total_width - left_width

            self.settings_column.setFixedWidth(left_width)
            self.summary_column.setFixedWidth(right_width)
            self.center_stage.setFixedWidth(final_center_width)
            self.center_stage.setFixedHeight(
                final_preview_total + self.CENTER_PANEL_GAP + final_log_total
            )
            self.preview_card.setFixedHeight(final_preview_total)
            self.log_card.setFixedHeight(final_log_total)
        finally:
            self._updating_right_layout = False

    def _update_lifecycle_visuals(self, text: str) -> None:
        if text == "运行中":
            state = "running"
        elif text == "启动中":
            state = "starting"
        elif text == "停止中":
            state = "stopped"
        elif text == "故障" or text.startswith("运行失败") or text.startswith("配置不可用"):
            state = "failed"
        elif text in {"已停止", "手动停止"}:
            state = "stopped"
        else:
            state = "idle"
        self._set_dynamic_property(self.preview_status_value, "statusState", state)

    def _make_card(
        self,
        object_name: str | None = None,
        *,
        layout_role: str | None = None,
    ) -> QFrame:
        card = QFrame()
        if object_name:
            card.setObjectName(object_name)
        card.setProperty("panelRole", "card")
        if layout_role:
            card.setProperty("layoutRole", layout_role)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        return card

    def _make_surface(self, *, layout_role: str | None = None) -> QFrame:
        frame = QFrame()
        frame.setProperty("panelRole", "surface")
        if layout_role:
            frame.setProperty("layoutRole", layout_role)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        return frame

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("textRole", "section")
        return label

    def _muted_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("textRole", "muted")
        return label

    def _create_combo_view(self) -> QListView:
        view = QListView()
        view.setProperty("viewRole", "comboPopup")
        view.setWordWrap(False)
        view.setSpacing(0)
        view.setUniformItemSizes(True)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        return view

    def _kv_row(self, key: str, value_label: QLabel) -> QHBoxLayout:
        value_label.setProperty(
            "textRole",
            "mono" if key in {"助战目标", "操作序列"} else "muted",
        )
        row = QHBoxLayout()
        row.setSpacing(6)
        key_label = QLabel(key)
        key_label.setProperty("textRole", "muted")
        row.addWidget(key_label)
        row.addStretch(1)
        row.addWidget(value_label, stretch=0)
        return row

    def _set_summary_value(self, label: QLabel, value: str) -> None:
        full_text = value or "-"
        label.setToolTip(full_text)
        label.setText(
            label.fontMetrics().elidedText(
                full_text,
                Qt.TextElideMode.ElideMiddle,
                label.maximumWidth(),
            )
        )

    def _set_config_status_saved(self) -> None:
        self.config_status_label.setText("✓ 已保存配置")
        self._set_dynamic_property(self.config_status_label, "noticeRole", "saved")

    def _set_config_status_dirty(self) -> None:
        self.config_status_label.setText("有未应用修改")
        self._set_dynamic_property(self.config_status_label, "noticeRole", "dirty")

    def _set_config_status_unavailable(self) -> None:
        self.config_status_label.setText(self._controller_config_error_text())
        self._set_dynamic_property(self.config_status_label, "noticeRole", "dirty")

    def _set_dynamic_property(self, widget: QWidget, name: str, value: str) -> None:
        widget.setProperty(name, value)
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()
