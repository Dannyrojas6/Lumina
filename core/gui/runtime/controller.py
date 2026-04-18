"""GUI 与主链之间的运行控制桥。"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QImage

from core.gui.services.runtime_service import (
    build_runtime_assembly,
    load_runtime_config,
)
from core.gui.services.runtime_config_service import (
    RuntimeEditableConfig,
    load_runtime_editable_config,
    save_runtime_editable_config,
)
from core.runtime.app import RuntimeAssembly, RuntimeEventCallbacks


def rgb_array_to_qimage(image_rgb: np.ndarray) -> QImage:
    """将 RGB ndarray 转成可跨线程传递的 QImage。"""
    height, width, channels = image_rgb.shape
    bytes_per_line = channels * width
    return QImage(
        image_rgb.data,
        width,
        height,
        bytes_per_line,
        QImage.Format.Format_RGB888,
    ).copy()


class RuntimeController(QObject):
    """运行控制器基础接口。"""

    log_emitted = Signal(str)
    state_changed = Signal(str)
    lifecycle_changed = Signal(str)
    preview_changed = Signal(QImage)
    running_changed = Signal(bool)
    error_occurred = Signal(str)
    summary_changed = Signal(str)

    def start(self) -> None:  # pragma: no cover - 子类覆盖
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - 子类覆盖
        raise NotImplementedError

    def load_editable_config(self) -> RuntimeEditableConfig:  # pragma: no cover
        raise NotImplementedError

    def apply_editable_config(self, config: RuntimeEditableConfig) -> None:  # pragma: no cover
        raise NotImplementedError


class GuiLogHandler(logging.Handler):
    """把项目日志转发给 GUI。"""

    def __init__(self, worker: "AutomationRuntimeWorker") -> None:
        super().__init__()
        self.worker = worker
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.worker.log_emitted.emit(self.format(record))
        except Exception:  # pragma: no cover - GUI 线程安全兜底
            self.handleError(record)


class AutomationRuntimeWorker(QThread):
    """在后台线程里运行现有主链。"""

    log_emitted = Signal(str)
    state_changed = Signal(str)
    preview_changed = Signal(QImage)
    run_completed = Signal()
    run_failed = Signal(str)

    def __init__(self, config_path: str | Path) -> None:
        super().__init__()
        self.config_path = Path(config_path)
        self._assembly: RuntimeAssembly | None = None

    def request_stop(self) -> None:
        """请求当前运行尽快结束。"""
        if self._assembly is not None:
            self._assembly.session.stop_requested = True

    def run(self) -> None:
        handler = GuiLogHandler(self)
        try:
            self._assembly = build_runtime_assembly(
                config_path=self.config_path,
                event_callbacks=RuntimeEventCallbacks(
                    on_state_changed=lambda state: self.state_changed.emit(state.name),
                    on_screen_rgb=lambda image_rgb: self.preview_changed.emit(
                        rgb_array_to_qimage(image_rgb)
                    ),
                ),
                extra_log_handlers=[handler],
            )
            self._assembly.engine.run()
            self.run_completed.emit()
        except Exception as exc:
            self.run_failed.emit(str(exc))
        finally:
            root_logger = logging.getLogger()
            if handler in root_logger.handlers:
                root_logger.removeHandler(handler)
            self._assembly = None


class AutomationRuntimeController(RuntimeController):
    """Qt 主程序对 Lumina 主链的运行控制器。"""

    def __init__(self, *, config_path: str | Path = "config/battle_config.yaml") -> None:
        super().__init__()
        self.config_path = Path(config_path)
        self._worker: AutomationRuntimeWorker | None = None
        self.current_summary = ""
        self._stop_requested = False
        self._completed_normally = False
        self._last_failure_message: str | None = None
        self.refresh_summary()

    def refresh_summary(self) -> None:
        """重新读取当前 battle_config 摘要。"""
        config = load_runtime_config(self.config_path)
        mode = f"battle_mode={config.battle_mode}"
        smart = f"smart_battle={'on' if config.smart_battle.enabled else 'off'}"
        support = f"support={config.support.class_name}/{config.support.servant or '-'}"
        sequence = config.custom_sequence_battle.sequence or "-"
        summary = "\n".join(
            [
                mode,
                smart,
                f"continue_battle={config.continue_battle}",
                f"log_level={config.log_level}",
                support,
                f"custom_sequence={sequence}",
            ]
        )
        self.current_summary = summary
        self.summary_changed.emit(summary)

    def load_editable_config(self) -> RuntimeEditableConfig:
        return load_runtime_editable_config(self.config_path)

    def apply_editable_config(self, config: RuntimeEditableConfig) -> None:
        save_runtime_editable_config(self.config_path, config)
        self.refresh_summary()

    def start(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.refresh_summary()
        self._stop_requested = False
        self._completed_normally = False
        self._last_failure_message = None
        worker = AutomationRuntimeWorker(self.config_path)
        worker.log_emitted.connect(self.log_emitted)
        worker.state_changed.connect(self.state_changed)
        worker.preview_changed.connect(self.preview_changed)
        worker.started.connect(self._on_worker_started)
        worker.run_failed.connect(self._on_worker_failed)
        worker.run_completed.connect(self._on_worker_completed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        self.lifecycle_changed.emit("启动中")
        worker.start()

    def stop(self) -> None:
        if self._worker is None or not self._worker.isRunning():
            return
        self._stop_requested = True
        self._worker.request_stop()
        self.lifecycle_changed.emit("手动停止")
        self.log_emitted.emit("已请求停止当前运行")

    def _on_worker_started(self) -> None:
        self.running_changed.emit(True)
        self.lifecycle_changed.emit("运行中")
        self.log_emitted.emit("GUI 已启动主链运行")

    def _on_worker_completed(self) -> None:
        self._completed_normally = True
        self.log_emitted.emit("主链运行结束")

    def _on_worker_failed(self, message: str) -> None:
        self._last_failure_message = message
        self.error_occurred.emit(message)
        self.lifecycle_changed.emit(f"运行失败：{message}")
        self.log_emitted.emit(f"运行异常：{message}")

    def _on_worker_finished(self) -> None:
        self.running_changed.emit(False)
        if self._last_failure_message is None:
            if self._stop_requested:
                self.lifecycle_changed.emit("手动停止")
            elif self._completed_normally:
                self.lifecycle_changed.emit("空闲")
            else:
                self.lifecycle_changed.emit("空闲")
        self._worker = None
