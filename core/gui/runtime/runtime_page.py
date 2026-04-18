"""主运行工作区页面。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.gui.runtime.controller import RuntimeController
from core.gui.services.runtime_config_service import RuntimeEditableConfig


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

    TOGGLE_CHECKBOX_STYLE = """
    QCheckBox {
        spacing: 0px;
        color: #d7dde5;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border-radius: 5px;
        border: 1px solid #66788a;
        background: #111821;
        image: none;
    }
    QCheckBox::indicator:hover {
        border-color: #8ca0b3;
        background: #1a2430;
    }
    QCheckBox::indicator:checked {
        border: 1px solid #8b5cf6;
        background: #8b5cf6;
        image: none;
    }
    QCheckBox::indicator:checked:hover {
        border-color: #7c3aed;
        background: #7c3aed;
    }
    """

    def __init__(self, runtime_controller: RuntimeController) -> None:
        super().__init__()
        self.runtime_controller = runtime_controller
        self._summary_text = getattr(runtime_controller, "current_summary", "") or "等待读取配置"
        self._saved_config = runtime_controller.load_editable_config()
        self._suppress_config_signals = False
        self._is_running = False
        self._build_ui()
        self._bind_controller()
        self._load_config_controls(self._saved_config)
        self._apply_summary(self._summary_text)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        content_row = QHBoxLayout()
        content_row.setSpacing(10)
        root.addLayout(content_row, stretch=1)

        self.left_card = QFrame()
        self.left_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.left_card.setFixedWidth(340)
        left_layout = QVBoxLayout(self.left_card)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("开始")
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addStretch(1)
        left_layout.addLayout(button_row)

        config_card = QFrame()
        config_card.setFrameShape(QFrame.Shape.StyledPanel)
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(12, 10, 12, 10)
        config_layout.setSpacing(8)
        config_layout.addWidget(QLabel("运行前配置"))

        config_form = QFormLayout()
        config_form.setContentsMargins(0, 0, 0, 0)
        config_form.setSpacing(8)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["main", "custom_sequence"])
        self.smart_battle_checkbox = QCheckBox()
        self.continue_battle_checkbox = QCheckBox()
        self.smart_battle_checkbox.setStyleSheet(self.TOGGLE_CHECKBOX_STYLE)
        self.continue_battle_checkbox.setStyleSheet(self.TOGGLE_CHECKBOX_STYLE)
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING"])
        config_form.addRow("模式", self.mode_combo)
        config_form.addRow("智能战斗", self.smart_battle_checkbox)
        config_form.addRow("连续出击", self.continue_battle_checkbox)
        config_form.addRow("日志级别", self.log_level_combo)
        config_layout.addLayout(config_form)

        config_buttons = QHBoxLayout()
        self.apply_button = QPushButton("应用")
        self.reset_button = QPushButton("恢复")
        config_buttons.addWidget(self.apply_button)
        config_buttons.addWidget(self.reset_button)
        config_buttons.addStretch(1)
        config_layout.addLayout(config_buttons)

        self.config_status_label = QLabel("已保存配置")
        self.config_status_label.setWordWrap(True)
        config_layout.addWidget(self.config_status_label)
        left_layout.addWidget(config_card)

        status_card = QFrame()
        status_card.setFrameShape(QFrame.Shape.StyledPanel)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(4)
        status_layout.addWidget(QLabel("当前状态"))
        self.status_value = QLabel("空闲")
        self.status_value.setObjectName("runtimeStatusValue")
        self.status_value.setStyleSheet("font-size:18px;font-weight:600;")
        self.status_value.setWordWrap(True)
        status_layout.addWidget(self.status_value)
        left_layout.addWidget(status_card)

        summary_card = QFrame()
        summary_card.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QFormLayout(summary_card)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(8)
        self.mode_value = QLabel("-")
        self.smart_value = QLabel("-")
        self.continue_value = QLabel("-")
        self.log_level_value = QLabel("-")
        self.support_value = QLabel("-")
        self.sequence_value = QLabel("-")
        self.support_value.setWordWrap(True)
        self.sequence_value.setWordWrap(True)
        summary_layout.addRow("模式", self.mode_value)
        summary_layout.addRow("智能战斗", self.smart_value)
        summary_layout.addRow("连续出击", self.continue_value)
        summary_layout.addRow("日志级别", self.log_level_value)
        summary_layout.addRow("助战目标", self.support_value)
        summary_layout.addRow("操作序列", self.sequence_value)
        left_layout.addWidget(summary_card)
        left_layout.addStretch(1)
        content_row.addWidget(self.left_card, stretch=0)

        self.preview_card = QFrame()
        self.preview_card.setFrameShape(QFrame.Shape.StyledPanel)
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)
        preview_layout.addWidget(QLabel("当前截图"))
        self.preview_label = self._StablePreviewLabel(
            preferred_size=QSize(760, 480),
            minimum_hint=QSize(640, 360),
        )
        self.preview_label.setText("等待画面")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setStyleSheet(
            "background:#10151b;border:1px solid #2d3946;"
        )
        preview_layout.addWidget(self.preview_label, stretch=1)
        content_row.addWidget(self.preview_card, stretch=1)

        self.log_frame = QFrame()
        self.log_frame.setFrameShape(QFrame.Shape.StyledPanel)
        log_layout = QVBoxLayout(self.log_frame)
        log_layout.setContentsMargins(12, 8, 12, 10)
        log_layout.setSpacing(6)
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("运行日志"))
        header_row.addStretch(1)
        self.log_toggle_button = QPushButton("展开")
        self.log_toggle_button.setFixedWidth(72)
        header_row.addWidget(self.log_toggle_button)
        log_layout.addLayout(header_row)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(160)
        self.log_output.setMaximumHeight(240)
        self.log_output.setVisible(False)
        log_layout.addWidget(self.log_output)
        self.log_frame.setMaximumHeight(44)
        root.addWidget(self.log_frame, stretch=0)

        self.start_button.clicked.connect(self._handle_start_clicked)
        self.stop_button.clicked.connect(self._handle_stop_clicked)
        self.log_toggle_button.clicked.connect(self._toggle_log_panel)
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
        if text == "启动中":
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
        self.config_status_label.setText("已保存配置")
        self._refresh_config_controls_enabled()

    def _handle_reset_clicked(self) -> None:
        self._saved_config = self.runtime_controller.load_editable_config()
        self._load_config_controls(self._saved_config)
        self.config_status_label.setText("已保存配置")
        self._refresh_config_controls_enabled()

    def append_log(self, message: str) -> None:
        self.log_output.append(message)

    def _toggle_log_panel(self) -> None:
        visible = self.log_output.isVisible()
        self.log_output.setVisible(not visible)
        self.log_toggle_button.setText("收起" if not visible else "展开")
        if visible:
            self.log_frame.setMaximumHeight(44)
        else:
            self.log_frame.setMaximumHeight(16777215)

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
        self.support_value.setText(values.get("support", "-"))
        self.sequence_value.setText(values.get("custom_sequence", "-"))

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
            self.config_status_label.setText("已保存配置")
        else:
            self.config_status_label.setText("有未应用修改")
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
