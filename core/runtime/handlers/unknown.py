"""未知状态处理器。"""

from __future__ import annotations

import logging

from core.perception import StateDetectionResult
from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameState

log = logging.getLogger("core.runtime.handlers.unknown")


class UnknownHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter
        self.fallback_templates = [
            ("close_upper_left.png", "未知状态兜底：已点击左上角关闭"),
            ("close.png", "未知状态兜底：已点击关闭"),
            ("next.png", "未知状态兜底：已点击下一步"),
            (
                "please_click_game_interface.png",
                "未知状态兜底：已点击请点击游戏界面",
            ),
        ]

    def handle(self, detection: StateDetectionResult) -> None:
        missing_count = len(detection.missing_templates)
        if detection.state == GameState.UNKNOWN:
            self.session.consecutive_unknown_count += 1
            if (
                self.session.consecutive_unknown_count >= 2
                and self._handle_unknown_fallback()
            ):
                self.session.consecutive_unknown_count = 0
                self.session.unknown_snapshot_saved = False
                return
            snapshot_path = None
            if not self.session.unknown_snapshot_saved:
                snapshot_path = self.session.save_unknown_snapshot()
                self.session.unknown_snapshot_saved = True
            if detection.best_match_state is not None:
                log.warning(
                    "未识别到已建模状态，最佳候选=%s score=%.2f template=%s screenshot=%s "
                    "missing_templates=%d unknown_snapshot=%s consecutive_unknown=%d，等待1s后重试",
                    detection.best_match_state.name,
                    detection.best_score,
                    detection.matched_template,
                    detection.screen_path,
                    missing_count,
                    snapshot_path,
                    self.session.consecutive_unknown_count,
                )
                return
            log.warning(
                "状态识别失败，未找到可用模板匹配 screenshot=%s missing_templates=%d "
                "unknown_snapshot=%s consecutive_unknown=%d，等待1s后重试",
                detection.screen_path,
                missing_count,
                snapshot_path,
                self.session.consecutive_unknown_count,
            )
            return

        self.session.consecutive_unknown_count = 0
        self.session.unknown_snapshot_saved = False
        log.warning(
            "检测到未处理状态=%s screenshot=%s，等待1s后重试",
            detection.state.name,
            detection.screen_path,
        )

    def _handle_unknown_fallback(self) -> bool:
        for template_name, message in self.fallback_templates:
            pos = self.session.recognizer.match(
                self.session.resources.template(template_name),
                self.session.get_latest_screen_image(),
            )
            if not pos:
                continue
            self.session.adb.click_raw(*pos)
            self.waiter.wait_seconds(message, 0.5)
            log.info(message)
            return True
        return False
