"""未知状态处理器。"""

from __future__ import annotations

import logging

from core.perception import StateDetectionResult
from core.runtime.handlers.battle_result import handle_ap_recovery_prompt
from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameState

log = logging.getLogger("core.runtime.handlers.unknown")


class UnknownHandler:
    FALLBACK_MIN_SCORE = 0.75
    AP_RECOVERY_BLOCKING_STATES = {
        GameState.LOADING_TIPS,
        GameState.SUPPORT_SELECT,
    }

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
            if self._should_attempt_ap_recovery_fallback(detection) and handle_ap_recovery_prompt(
                self.session,
                self.waiter,
                appear_timeout=0.0,
                appear_poll_interval=0.25,
                template_timeout=10.0,
                template_poll_interval=0.5,
                destination_timeout=45.0,
                destination_poll_interval=0.5,
            ):
                self.session.consecutive_unknown_count = 0
                self.session.unknown_snapshot_saved = False
                log.info("未知状态已识别为行动力恢复界面，已完成恢复流程")
                return
            self.session.consecutive_unknown_count += 1
            if (
                self.session.consecutive_unknown_count >= 2
                and self._handle_unknown_fallback(detection)
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

    def _handle_unknown_fallback(self, detection: StateDetectionResult) -> bool:
        best_state = detection.best_match_state
        if best_state is None or detection.best_score < self.FALLBACK_MIN_SCORE:
            return False
        for template_name, message in self.fallback_templates:
            if not self._fallback_allowed_for_state(template_name, best_state):
                continue
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

    def _should_attempt_ap_recovery_fallback(
        self,
        detection: StateDetectionResult,
    ) -> bool:
        return detection.best_match_state not in self.AP_RECOVERY_BLOCKING_STATES

    @staticmethod
    def _fallback_allowed_for_state(
        template_name: str,
        best_state: GameState,
    ) -> bool:
        if template_name == "next.png":
            return best_state == GameState.BATTLE_RESULT
        if template_name in {"close_upper_left.png", "close.png"}:
            return best_state == GameState.DIALOG
        return False
