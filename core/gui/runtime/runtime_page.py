"""主运行工作区页面。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
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
    QSplitter,
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

    class _StablePreviewLabel(QLabel):
        """避免截图更新后改变页面尺寸提示。"""

        def __init__(self, preferred_size: QSize, minimum_hint: QSize) -> None:
            super().__init__()
            self._preferred_size = QSize(preferred_size)
            self._minimum_hint = QSize(minimum_hint)

        def sizeHint(self) -> QSize:  # type: ignore[override]
            return QSize(self._preferred_size)

        def minimumSizeHint(self) -> QSize:  # type: ignore[override]
            return QSize(self._minimum_hint)

    def __init__(
        self,
        runtime_controller: RuntimeController,
    ) -> None:
        super().__init__()
        self.runtime_controller = runtime_controller
        self._summary_text = getattr(runtime_controller, "current_summary", "") or "等待读取配置"
        self._saved_config = runtime_controller.load_editable_config()
        self._suppress_config_signals = False
        self._is_running = False
        self._log_dialog: QDialog | None = None
        self._log_dialog_output: QTextEdit | None = None
        self._build_ui()
        self._bind_controller()
        self._load_config_controls(self._saved_config)
        self._apply_summary(self._summary_text)
        self._update_lifecycle_visuals("空闲")

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.left_card = self._make_card("runtimeLeftCard", layout_role="sidePanel")
        self.left_card.setFixedWidth(210)
        left_layout = QVBoxLayout(self.left_card)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self.start_button = QPushButton("▶ 开始")
        self.start_button.setObjectName("successButton")
        self.start_button.setFixedHeight(30)
        self.stop_button = QPushButton("■ 停止")
        self.stop_button.setEnabled(False)
        self.stop_button.setFixedHeight(30)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        left_layout.addLayout(button_row)

        config_card = self._make_card()
        config_layout = QVBoxLayout(config_card)
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
        config_grid.addWidget(self.mode_combo, 0, 1)
        config_grid.addWidget(self._muted_label("智能战斗"), 1, 0)
        config_grid.addWidget(self.smart_battle_checkbox, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        config_grid.addWidget(self._muted_label("连续出击"), 2, 0)
        config_grid.addWidget(self.continue_battle_checkbox, 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
        config_grid.addWidget(self._muted_label("日志级别"), 3, 0)
        config_grid.addWidget(self.log_level_combo, 3, 1)
        config_layout.addLayout(config_grid)

        config_buttons = QHBoxLayout()
        config_buttons.setSpacing(5)
        self.apply_button = QPushButton("应用")
        self.apply_button.setObjectName("primaryButton")
        self.reset_button = QPushButton("恢复")
        config_buttons.addWidget(self.apply_button)
        config_buttons.addWidget(self.reset_button)
        config_layout.addLayout(config_buttons)

        self.config_status_label = QLabel()
        self._set_config_status_saved()
        config_layout.addWidget(self.config_status_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        left_layout.addWidget(config_card)

        status_card = self._make_card()
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(10, 8, 10, 8)
        status_layout.setSpacing(8)
        status_layout.addWidget(self._section_label("当前状态"))
        status_row = QHBoxLayout()
        status_row.setSpacing(7)
        status_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.status_dot = QLabel()
        self.status_dot.setObjectName("runtimeStatusDot")
        self.status_dot.setFixedSize(8, 8)
        status_row.addWidget(self.status_dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.status_value = QLabel("空闲")
        self.status_value.setObjectName("runtimeStatusValue")
        self.status_value.setProperty("statusState", "idle")
        self.status_value.setWordWrap(True)
        self.status_value.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        status_row.addWidget(self.status_value, stretch=1)
        status_layout.addLayout(status_row)
        left_layout.addWidget(status_card)

        summary_card = self._make_card()
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(6)
        summary_layout.addWidget(self._section_label("当前已保存配置"))
        self.mode_value = QLabel("-")
        self.smart_value = QLabel("-")
        self.continue_value = QLabel("-")
        self.log_level_value = QLabel("-")
        self.support_value = QLabel("-")
        self.sequence_value = QLabel("-")
        self.support_value.setWordWrap(False)
        self.sequence_value.setWordWrap(False)
        self.support_value.setMaximumWidth(120)
        self.sequence_value.setMaximumWidth(120)
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
        left_layout.addWidget(summary_card)
        left_layout.addStretch(1)
        root.addWidget(self.left_card, stretch=0)

        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.preview_card = self._make_surface(layout_role="canvasPanel")
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        self.preview_label = self._StablePreviewLabel(
            preferred_size=QSize(760, 380),
            minimum_hint=QSize(620, 320),
        )
        self.preview_label.setText("等待画面")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.preview_label.setMinimumSize(620, 320)
        self.preview_label.setObjectName("runtimePreviewViewport")
        preview_layout.addWidget(self.preview_label, stretch=1)
        right_layout.addWidget(self.preview_card, stretch=1)

        self.log_card = self._make_surface(layout_role="canvasPanel")
        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)
        self.log_head_widget = QWidget()
        self.log_head_widget.setProperty("headerRole", "panel")
        self.log_head_widget.setFixedHeight(34)
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
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.setHandleWidth(6)
        self.right_splitter.addWidget(self.preview_card)
        self.right_splitter.addWidget(self.log_card)
        self.right_splitter.setSizes([430, 180])
        right_layout.addWidget(self.right_splitter, stretch=1)
        root.addWidget(right_column, stretch=1)

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

    def _bind_controller(self) -> None:
        self.runtime_controller.lifecycle_changed.connect(self.set_status_text)
        self.runtime_controller.preview_changed.connect(self.set_preview_image)
        self.runtime_controller.running_changed.connect(self.set_running_state)
        self.runtime_controller.summary_changed.connect(self.set_summary_text)
        self.runtime_controller.log_emitted.connect(self.append_log)

    def set_running_state(self, is_running: bool) -> None:
        self._is_running = is_running
        self.start_button.setEnabled(not is_running)
        self.stop_button.setEnabled(is_running)
        self._refresh_config_controls_enabled()

    def set_status_text(self, text: str) -> None:
        self.status_value.setText(text)
        self._update_lifecycle_visuals(text)
        if text == "启动中":
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
        if text == "停止中":
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
        self._refresh_config_controls_enabled()

    def set_summary_text(self, summary: str) -> None:
        self._summary_text = summary
        self._apply_summary(summary)

    def set_preview_image(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setText("")

    def _handle_start_clicked(self) -> None:
        self.set_status_text("启动中")
        self.runtime_controller.start()

    def _handle_stop_clicked(self) -> None:
        self.runtime_controller.stop()

    def _handle_apply_clicked(self) -> None:
        config = self._build_current_config()
        self.runtime_controller.apply_editable_config(config)
        self._saved_config = config
        self._load_config_controls(config)
        self._set_config_status_saved()
        self._refresh_config_controls_enabled()

    def _handle_reset_clicked(self) -> None:
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
        self._sync_mode_controls()
        if self._build_current_config() == self._saved_config:
            self._set_config_status_saved()
        else:
            self._set_config_status_dirty()
        self._refresh_config_controls_enabled()

    def _sync_mode_controls(self) -> None:
        self.smart_battle_checkbox.setEnabled(
            self.mode_combo.currentText() == "main" and self._controls_editable()
        )

    def _controls_editable(self) -> bool:
        return not self._is_running and self.status_value.text() != "启动中"

    def _refresh_config_controls_enabled(self) -> None:
        editable = self._controls_editable()
        self.mode_combo.setEnabled(editable)
        self.continue_battle_checkbox.setEnabled(editable)
        self.log_level_combo.setEnabled(editable)
        self._sync_mode_controls()
        dirty = self._build_current_config() != self._saved_config
        self.apply_button.setEnabled(editable and dirty)
        self.reset_button.setEnabled(editable and dirty)

    def _update_lifecycle_visuals(self, text: str) -> None:
        if text == "运行中":
            state = "running"
        elif text == "启动中":
            state = "starting"
        elif text == "停止中":
            state = "stopped"
        elif text.startswith("运行失败"):
            state = "failed"
        elif text == "手动停止":
            state = "stopped"
        else:
            state = "idle"
        self._set_dynamic_property(self.status_dot, "statusState", state)
        self._set_dynamic_property(self.status_value, "statusState", state)

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
                120,
            )
        )

    def _set_config_status_saved(self) -> None:
        self.config_status_label.setText("✓ 已保存配置")
        self._set_dynamic_property(self.config_status_label, "noticeRole", "saved")

    def _set_config_status_dirty(self) -> None:
        self.config_status_label.setText("有未应用修改")
        self._set_dynamic_property(self.config_status_label, "noticeRole", "dirty")

    def _set_dynamic_property(self, widget: QWidget, name: str, value: str) -> None:
        widget.setProperty(name, value)
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()
