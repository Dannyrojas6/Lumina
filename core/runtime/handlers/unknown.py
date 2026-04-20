"""未知状态处理器。"""

from __future__ import annotations

import logging
import time

from core.perception import StateDetectionResult
from core.runtime.handlers.battle_result import handle_ap_recovery_prompt
from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameState

log = logging.getLogger("core.runtime.handlers.unknown")


class UnknownHandler:
    FALLBACK_MIN_SCORE = 0.75
    FALLBACK_COOLDOWN_SECONDS = 2.0
    FALLBACK_PROGRESS_WAIT_SECONDS = 0.5
    MAX_FALLBACK_ATTEMPTS = 2
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
        if getattr(self.session, "stop_requested", False):
            return
        missing_count = len(detection.missing_templates)
        if detection.state == GameState.UNKNOWN:
            previous_unknown_count = self.session.consecutive_unknown_count
            self.session.consecutive_unknown_count += 1
            if previous_unknown_count == 0:
                self.session.unknown_snapshot_saved = False
                self.session.unknown_fallback_attempts_this_turn = 0
                self.session.unknown_last_fallback_template = None
                self.session.unknown_last_fallback_click_time = None
                self.session.ap_recovery_consecutive_hits = 0
                self.session.ap_recovery_window_started_at = None
                self.session.ap_recovery_last_hit_time = None
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
                self._reset_unknown_runtime_state()
                log.info("未知状态已识别为行动力恢复界面，已完成恢复流程")
                return
            if self.session.consecutive_unknown_count < 2:
                self._record_unknown_snapshot(detection, missing_count)
                return
            if self.session.unknown_fallback_attempts_this_turn >= self.MAX_FALLBACK_ATTEMPTS:
                self._stop_unknown(
                    "UNKNOWN 连续兜底后仍无进展，已停止运行"
                )
                return
            self._record_unknown_snapshot(detection, missing_count)
            if self._handle_unknown_fallback(detection):
                return
            return

        self._reset_unknown_runtime_state()
        log.warning(
            "检测到未处理状态=%s screenshot=%s",
            detection.state.name,
            detection.screen_path,
        )

    def _handle_unknown_fallback(self, detection: StateDetectionResult) -> bool:
        best_state = detection.best_match_state
        if best_state is None or detection.best_score < self.FALLBACK_MIN_SCORE:
            return False
        template_name, message = self._select_fallback_template(best_state)
        if template_name is None:
            return False
        now = time.monotonic()
        if (
            self.session.unknown_last_fallback_template == template_name
            and self.session.unknown_last_fallback_click_time is not None
            and now - self.session.unknown_last_fallback_click_time
            < self.FALLBACK_COOLDOWN_SECONDS
        ):
            log.info(
                "未知状态兜底模板仍在冷却期 template=%s elapsed=%.2f",
                template_name,
                now - self.session.unknown_last_fallback_click_time,
            )
            return False
        pos = self.session.recognizer.match(
            self.session.resources.template(template_name),
            self.session.get_latest_screen_image(),
        )
        if not pos:
            return False
        self.session.adb.click_raw(*pos)
        self.session.unknown_fallback_attempts_this_turn += 1
        self.session.unknown_last_fallback_template = template_name
        self.session.unknown_last_fallback_click_time = now
        self.waiter.wait_seconds(message, self.FALLBACK_PROGRESS_WAIT_SECONDS)
        progress = self._unknown_fallback_made_progress(template_name)
        if progress:
            log.info(message)
            return True
        if self.session.unknown_fallback_attempts_this_turn >= self.MAX_FALLBACK_ATTEMPTS:
            self._stop_unknown("UNKNOWN 连续兜底后仍无进展，已停止运行")
            return True
        log.warning(
            "未知状态兜底后仍未观察到进展 template=%s attempts=%d",
            template_name,
            self.session.unknown_fallback_attempts_this_turn,
        )
        return True

    def _record_unknown_snapshot(
        self,
        detection: StateDetectionResult,
        missing_count: int,
    ) -> str | None:
        snapshot_path = None
        if not self.session.unknown_snapshot_saved:
            snapshot_path = self.session.save_unknown_snapshot()
            self.session.unknown_snapshot_saved = bool(snapshot_path)
        if detection.best_match_state is not None:
            log.warning(
                "未识别到已建模状态，最佳候选=%s score=%.2f template=%s screenshot=%s "
                "missing_templates=%d unknown_snapshot=%s consecutive_unknown=%d",
                detection.best_match_state.name,
                detection.best_score,
                detection.matched_template,
                detection.screen_path,
                missing_count,
                snapshot_path,
                self.session.consecutive_unknown_count,
            )
            return snapshot_path
        log.warning(
            "状态识别失败，未找到可用模板匹配 screenshot=%s missing_templates=%d "
            "unknown_snapshot=%s consecutive_unknown=%d",
            detection.screen_path,
            missing_count,
            snapshot_path,
            self.session.consecutive_unknown_count,
        )
        return snapshot_path

    def _select_fallback_template(
        self,
        best_state: GameState,
    ) -> tuple[str | None, str | None]:
        for template_name, message in self.fallback_templates:
            if not self._fallback_allowed_for_state(template_name, best_state):
                continue
            return template_name, message
        return None, None

    def _unknown_fallback_made_progress(self, template_name: str) -> bool:
        self.session.refresh_screen()
        post_detection = self.waiter.state_detector.detect()
        if post_detection.state != GameState.UNKNOWN:
            self._reset_unknown_runtime_state()
            log.info(
                "未知状态兜底后已切换到 %s",
                post_detection.state.name,
            )
            return True

        template_path = self.session.resources.template(template_name)
        still_matches = self.session.recognizer.match(
            template_path,
            self.session.get_latest_screen_image(),
        )
        if not still_matches:
            self._reset_unknown_runtime_state()
            log.info("未知状态兜底后模板已不再命中 template=%s", template_name)
            return True
        return False

    def _stop_unknown(self, reason: str) -> None:
        self.session.stop_requested = True
        raise RuntimeError(reason)

    def _reset_unknown_runtime_state(self) -> None:
        reset = getattr(self.session, "reset_unknown_runtime_state", None)
        if callable(reset):
            reset()
            return
        self.session.unknown_snapshot_saved = False
        self.session.consecutive_unknown_count = 0
        self.session.unknown_fallback_attempts_this_turn = 0
        self.session.unknown_last_fallback_template = None
        self.session.unknown_last_fallback_click_time = None
        self.session.ap_recovery_consecutive_hits = 0
        self.session.ap_recovery_window_started_at = None
        self.session.ap_recovery_last_hit_time = None

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
        
    def _should_attempt_ap_recovery_fallback(
        self,
        detection: StateDetectionResult,
    ) -> bool:
        return detection.best_match_state not in self.AP_RECOVERY_BLOCKING_STATES
