"""GUI 运行子进程入口。"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any

import cv2
import numpy as np

from core.gui.services.runtime_service import build_runtime_assembly
from core.runtime.app import RuntimeEventCallbacks


def encode_preview_image(image_rgb: np.ndarray) -> bytes | None:
    """将 RGB 画面压缩成 PNG 字节，便于跨进程传递。"""
    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    success, encoded = cv2.imencode(".png", image_bgr)
    if not success:
        return None
    return encoded.tobytes()


class QueueLogHandler(logging.Handler):
    """将子进程日志转发给父进程。"""

    def __init__(self, event_queue: Any) -> None:
        super().__init__()
        self.event_queue = event_queue
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.event_queue.put(
                {
                    "type": "log",
                    "message": self.format(record),
                }
            )
        except Exception:
            self.handleError(record)


def run_runtime_process(
    *,
    config_path: str,
    event_queue: Any,
    control_queue: Any,
) -> None:
    """在独立子进程里运行主链，并通过队列回传事件。"""
    stop_requested = threading.Event()
    assembly_holder: dict[str, Any] = {}

    def _control_loop() -> None:
        while not stop_requested.is_set():
            try:
                command = control_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except Exception:
                return
            if command == "stop":
                stop_requested.set()
                assembly = assembly_holder.get("assembly")
                if assembly is not None:
                    assembly.session.stop_requested = True
                return

    control_thread = threading.Thread(target=_control_loop, daemon=True)
    control_thread.start()

    log_handler = QueueLogHandler(event_queue)
    root_logger = logging.getLogger()
    try:
        assembly = build_runtime_assembly(
            config_path=config_path,
            event_callbacks=RuntimeEventCallbacks(
                on_state_changed=lambda state: event_queue.put(
                    {"type": "state", "state": state.name}
                ),
                on_screen_rgb=lambda image_rgb: _emit_preview(
                    event_queue=event_queue,
                    image_rgb=image_rgb,
                ),
            ),
            extra_log_handlers=[log_handler],
        )
        assembly_holder["assembly"] = assembly
        if stop_requested.is_set():
            assembly.session.stop_requested = True
        event_queue.put({"type": "started"})
        assembly.engine.run()
        if not stop_requested.is_set():
            event_queue.put({"type": "completed"})
    except Exception as exc:
        if not stop_requested.is_set():
            event_queue.put({"type": "failed", "message": str(exc)})
    finally:
        if log_handler in root_logger.handlers:
            root_logger.removeHandler(log_handler)
        stop_requested.set()


def _emit_preview(*, event_queue: Any, image_rgb: np.ndarray) -> None:
    payload = encode_preview_image(image_rgb)
    if payload is None:
        return
    event_queue.put({"type": "preview", "image_bytes": payload})
