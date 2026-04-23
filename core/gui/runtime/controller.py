"""GUI 与主链之间的运行控制桥。"""

from __future__ import annotations

import multiprocessing
import queue
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QImage

from core.gui.services.runtime_service import (
    load_runtime_config,
)
from core.gui.services.runtime_config_service import (
    RuntimeEditableConfig,
    load_runtime_editable_config,
    save_runtime_editable_config,
)
from core.gui.runtime.worker_process import run_runtime_process


def image_bytes_to_qimage(image_bytes: bytes) -> QImage:
    """将压缩图片字节还原为 QImage。"""
    image = QImage()
    image.loadFromData(image_bytes)
    return image


class RuntimeController(QObject):
    """运行控制器基础接口。"""

    log_emitted = Signal(str)
    state_changed = Signal(str)
    lifecycle_changed = Signal(str)
    preview_changed = Signal(QImage)
    running_changed = Signal(bool)
    error_occurred = Signal(str)
    summary_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_summary = ""
        self.current_lifecycle_text = "空闲"
        self.current_config_error: str | None = None
        self.config_available = True

    def start(self) -> None:  # pragma: no cover - 子类覆盖
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - 子类覆盖
        raise NotImplementedError

    def load_editable_config(self) -> RuntimeEditableConfig:  # pragma: no cover
        raise NotImplementedError

    def apply_editable_config(self, config: RuntimeEditableConfig) -> None:  # pragma: no cover
        raise NotImplementedError


class AutomationRuntimeWorker(QThread):
    """在后台线程里监管一次运行子进程。"""

    TERMINATE_GRACE_SECONDS = 0.5
    KILL_GRACE_SECONDS = 1.5

    log_emitted = Signal(str)
    state_changed = Signal(str)
    preview_changed = Signal(QImage)
    run_started = Signal()
    run_completed = Signal()
    run_failed = Signal(str)

    def __init__(self, config_path: str | Path) -> None:
        super().__init__()
        self.config_path = Path(config_path)
        self._context = multiprocessing.get_context("spawn")
        self._process = None
        self._control_queue = None
        self._event_queue = None
        self._stop_requested = False
        self._terminate_sent = False
        self._kill_sent = False
        self._terminate_deadline = 0.0
        self._kill_deadline = 0.0
        self._completed_normally = False
        self._failure_message: str | None = None

    def request_stop(self) -> None:
        """请求当前运行尽快结束，并启动强退宽限。"""
        self._stop_requested = True
        if self._control_queue is not None:
            try:
                self._control_queue.put_nowait("stop")
            except Exception:
                pass
        now = time.monotonic()
        self._terminate_deadline = now + self.TERMINATE_GRACE_SECONDS
        self._kill_deadline = self._terminate_deadline + self.KILL_GRACE_SECONDS

    def run(self) -> None:
        self._completed_normally = False
        self._failure_message = None
        self._stop_requested = False
        self._terminate_sent = False
        self._kill_sent = False
        self._control_queue = self._context.Queue()
        self._event_queue = self._context.Queue()
        process = self._context.Process(
            target=run_runtime_process,
            kwargs={
                "config_path": str(self.config_path),
                "event_queue": self._event_queue,
                "control_queue": self._control_queue,
            },
            daemon=True,
        )
        self._process = process
        try:
            process.start()
            while True:
                self._drain_event(timeout=0.1)
                self._enforce_stop_deadlines(time.monotonic())
                if not process.is_alive():
                    break
            self._drain_remaining_events()
            process.join(timeout=0.5)

            if self._stop_requested:
                return
            if self._failure_message is not None:
                self.run_failed.emit(self._failure_message)
                return
            if self._completed_normally:
                self.run_completed.emit()
                return
            self.run_failed.emit("运行子进程意外退出")
        except Exception as exc:
            if not self._stop_requested:
                self.run_failed.emit(str(exc))
        finally:
            self._cleanup_process_resources()

    def _drain_event(self, *, timeout: float) -> None:
        if self._event_queue is None:
            return
        try:
            event = self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return
        self._handle_event(event)

    def _drain_remaining_events(self) -> None:
        if self._event_queue is None:
            return
        while True:
            try:
                event = self._event_queue.get_nowait()
            except queue.Empty:
                return
            self._handle_event(event)

    def _handle_event(self, event: dict[str, object]) -> None:
        event_type = str(event.get("type", ""))
        if self._stop_requested and event_type in {
            "log",
            "state",
            "preview",
            "failed",
            "completed",
            "started",
        }:
            return

        if event_type == "log":
            self.log_emitted.emit(str(event.get("message", "")))
            return
        if event_type == "state":
            self.state_changed.emit(str(event.get("state", "")))
            return
        if event_type == "preview":
            image_bytes = event.get("image_bytes")
            if isinstance(image_bytes, bytes):
                self.preview_changed.emit(image_bytes_to_qimage(image_bytes))
            return
        if event_type == "started":
            self.run_started.emit()
            return
        if event_type == "completed":
            self._completed_normally = True
            return
        if event_type == "failed":
            self._failure_message = str(event.get("message", ""))

    def _enforce_stop_deadlines(self, now: float) -> None:
        process = self._process
        if (
            not self._stop_requested
            or process is None
            or not process.is_alive()
        ):
            return
        if not self._terminate_sent and now >= self._terminate_deadline:
            process.terminate()
            self._terminate_sent = True
            return
        if self._terminate_sent and not self._kill_sent and now >= self._kill_deadline:
            process.kill()
            self._kill_sent = True

    def _cleanup_process_resources(self) -> None:
        process = self._process
        if process is not None:
            if process.pid is not None:
                if process.is_alive():
                    process.kill()
                process.join(timeout=0.2)
        if self._control_queue is not None:
            self._control_queue.close()
        if self._event_queue is not None:
            self._event_queue.close()
        self._process = None
        self._control_queue = None
        self._event_queue = None


class AutomationRuntimeController(RuntimeController):
    """Qt 主程序对 Lumina 主链的运行控制器。"""

    CONFIG_UNAVAILABLE_SUMMARY = "\n".join(
        [
            "loop_count=-",
            "battle_mode=配置不可用",
            "smart_battle=-",
            "continue_battle=-",
            "log_level=-",
            "support=-",
            "custom_sequence=-",
        ]
    )
    _PLACEHOLDER_EDITABLE_CONFIG = RuntimeEditableConfig(
        loop_count=10,
        battle_mode="main",
        smart_battle_enabled=False,
        continue_battle=True,
        log_level="INFO",
    )

    def __init__(
        self,
        *,
        config_path: str | Path = "config/battle_config.yaml",
        worker_factory=None,
    ) -> None:
        super().__init__()
        self.config_path = Path(config_path)
        self._worker: AutomationRuntimeWorker | None = None
        self._worker_factory = worker_factory or (lambda path: AutomationRuntimeWorker(path))
        self._stop_requested = False
        self._completed_normally = False
        self._last_failure_message: str | None = None
        self.refresh_summary()

    def refresh_summary(self) -> None:
        """重新读取当前 battle_config 摘要。"""
        try:
            config = load_runtime_config(self.config_path)
        except Exception as exc:
            self._set_config_unavailable(str(exc) or exc.__class__.__name__)
            return

        mode = f"battle_mode={config.battle_mode}"
        loop_count = f"loop_count={config.loop_count}"
        smart = f"smart_battle={'on' if config.smart_battle.enabled else 'off'}"
        support = f"support={config.support.class_name}/{config.support.servant or '-'}"
        sequence = config.custom_sequence_battle.sequence or "-"
        summary = "\n".join(
            [
                loop_count,
                mode,
                smart,
                f"continue_battle={config.continue_battle}",
                f"log_level={config.log_level}",
                support,
                f"custom_sequence={sequence}",
            ]
        )
        self.config_available = True
        self.current_config_error = None
        self.current_summary = summary
        self.summary_changed.emit(summary)
        if self._worker is None or not self._worker.isRunning():
            self._set_lifecycle("空闲")

    def load_editable_config(self) -> RuntimeEditableConfig:
        if not self.config_available:
            return self._PLACEHOLDER_EDITABLE_CONFIG
        try:
            return load_runtime_editable_config(self.config_path)
        except Exception as exc:
            self._set_config_unavailable(str(exc) or exc.__class__.__name__)
            return self._PLACEHOLDER_EDITABLE_CONFIG

    def apply_editable_config(self, config: RuntimeEditableConfig) -> None:
        if not self.config_available:
            raise RuntimeError("配置不可用，无法应用运行前修改。")
        save_runtime_editable_config(self.config_path, config)
        self.refresh_summary()

    def start(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.refresh_summary()
        if not self.config_available:
            return
        self._stop_requested = False
        self._completed_normally = False
        self._last_failure_message = None
        worker = self._worker_factory(self.config_path)
        worker.log_emitted.connect(self.log_emitted)
        worker.state_changed.connect(self.state_changed)
        worker.preview_changed.connect(self.preview_changed)
        worker.run_started.connect(self._on_worker_started)
        worker.run_failed.connect(self._on_worker_failed)
        worker.run_completed.connect(self._on_worker_completed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        self._set_lifecycle("启动中")
        worker.start()

    def stop(self) -> None:
        if self._worker is None or not self._worker.isRunning():
            return
        self._stop_requested = True
        self._worker.request_stop()
        self._set_lifecycle("停止中")
        self.log_emitted.emit("已请求强制停止当前运行")

    def _on_worker_started(self) -> None:
        self.running_changed.emit(True)
        self._set_lifecycle("运行中")
        self.log_emitted.emit("GUI 已启动主链运行")

    def _on_worker_completed(self) -> None:
        if self._stop_requested:
            return
        self._completed_normally = True
        self.log_emitted.emit("主链运行结束")

    def _on_worker_failed(self, message: str) -> None:
        if self._stop_requested:
            return
        self._last_failure_message = message
        self.error_occurred.emit(message)
        self._set_lifecycle("故障")
        self.log_emitted.emit(f"运行异常：{message}")

    def _on_worker_finished(self) -> None:
        self.running_changed.emit(False)
        if self._last_failure_message is None:
            if self._stop_requested:
                self._set_lifecycle("已停止")
            elif self._completed_normally:
                self._set_lifecycle("空闲")
            else:
                self._set_lifecycle("空闲")
        self._worker = None

    def _set_lifecycle(self, text: str) -> None:
        self.current_lifecycle_text = text
        self.lifecycle_changed.emit(text)

    def _set_config_unavailable(self, message: str) -> None:
        self.config_available = False
        self.current_config_error = message
        self.current_summary = self.CONFIG_UNAVAILABLE_SUMMARY
        self.summary_changed.emit(self.current_summary)
        self._set_lifecycle("故障")
        self.error_occurred.emit(message)
