"""运行时等待与同步。"""

from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import cv2
import numpy as np

from core.perception import StateDetectionResult, StateDetector
from core.runtime.session import RuntimeSession
from core.shared import GameCoordinates, GameState

log = logging.getLogger("core.runtime.waiter")


class Waiter:
    """集中管理页面级等待逻辑。"""

    def __init__(self, session: RuntimeSession, state_detector: StateDetector) -> None:
        self.session = session
        self.state_detector = state_detector

    def wait_seconds(self, reason: str, seconds: float) -> None:
        log.info("%s，等待 %.1f 秒", reason, seconds)
        time.sleep(seconds)

    def confirm_state_entry(self, state: GameState) -> bool:
        """在处理高风险页面前，先确认页面内容已经稳定。"""
        if state == GameState.SUPPORT_SELECT:
            return self.wait_screen_stable(
                region=GameCoordinates.SUPPORT_PORTRAIT_STRIP,
                stable_frames=1,
                timeout=2.5,
                poll_interval=0.25,
            )

        if state == GameState.CARD_SELECT:
            return True

        if state == GameState.BATTLE_RESULT:
            return True

        return True

    def wait_state_exit(
        self,
        states: Iterable[GameState],
        *,
        timeout: float,
        poll_interval: float,
    ) -> Optional[StateDetectionResult]:
        watched = set(states)
        deadline = time.time() + max(0.0, timeout)
        while time.time() < deadline:
            self.session.refresh_screen()
            screen = self.session.get_latest_screen_image()
            if self._matches_watched_state(screen, watched):
                time.sleep(poll_interval)
                continue

            detection = self.state_detector.detect()
            if detection.state not in watched:
                return detection
            time.sleep(poll_interval)
        return None

    def wait_post_card_battle_end(
        self,
        *,
        timeout: float,
        poll_interval: float,
        stable_hits: int,
    ) -> GameState | None:
        deadline = time.time() + max(0.0, timeout)
        ready_template = self.session.resources.state_templates[GameState.BATTLE_READY]
        result_templates = self.session.resources.state_templates[GameState.BATTLE_RESULT]
        if not isinstance(result_templates, tuple):
            result_templates = (result_templates,)

        previous_family: str | None = None
        consecutive_hits = 0
        while time.time() < deadline:
            self.session.refresh_screen()
            screen = self.session.get_latest_screen_image()
            current_family = self._detect_post_card_family(
                ready_template=ready_template,
                result_templates=result_templates,
                screen=screen,
            )
            if current_family is None:
                previous_family = None
                consecutive_hits = 0
                time.sleep(poll_interval)
                continue

            if current_family == previous_family:
                consecutive_hits += 1
            else:
                previous_family = current_family
                consecutive_hits = 1

            if consecutive_hits >= stable_hits:
                if current_family == "battle_ready":
                    return GameState.BATTLE_READY
                if current_family == "battle_result":
                    return GameState.BATTLE_RESULT

            time.sleep(poll_interval)
        return None

    def wait_template_disappear(
        self,
        template_path: str,
        *,
        timeout: float,
        poll_interval: float,
    ) -> bool:
        deadline = time.time() + max(0.0, timeout)
        while time.time() < deadline:
            if not self.session.recognizer.match(
                template_path,
                self.session.get_latest_screen_image(),
            ):
                return True
            time.sleep(poll_interval)
            self.session.refresh_screen()
        return False

    def wait_screen_stable(
        self,
        *,
        region: tuple[int, int, int, int] | None = None,
        stable_frames: int = 2,
        timeout: float,
        poll_interval: float,
    ) -> bool:
        deadline = time.time() + max(0.0, timeout)
        previous = self._extract_region(self.session.get_latest_screen_image(), region)
        stable_count = 0
        while time.time() < deadline:
            time.sleep(poll_interval)
            self.session.refresh_screen()
            current = self._extract_region(self.session.get_latest_screen_image(), region)
            if self._is_stable(previous, current):
                stable_count += 1
                if stable_count >= stable_frames:
                    return True
            else:
                stable_count = 0
            previous = current
        return False

    def _extract_region(
        self,
        image: np.ndarray,
        region: tuple[int, int, int, int] | None,
    ) -> np.ndarray:
        if region is None:
            return image.copy()
        x1, y1, x2, y2 = region
        return image[y1:y2, x1:x2].copy()

    def _is_stable(self, previous: np.ndarray, current: np.ndarray) -> bool:
        if previous.shape != current.shape:
            return False
        diff = cv2.absdiff(previous, current)
        return float(np.mean(diff)) <= 1.0

    def _detect_post_card_family(
        self,
        *,
        ready_template: str,
        result_templates: tuple[str, ...],
        screen: np.ndarray,
    ) -> str | None:
        if self.session.recognizer.match(ready_template, screen):
            return "battle_ready"
        for template_path in result_templates:
            if self.session.recognizer.match(template_path, screen):
                return "battle_result"
        return None

    def _matches_watched_state(
        self,
        screen: np.ndarray,
        watched: set[GameState],
    ) -> bool:
        for state in watched:
            if state == GameState.UNKNOWN:
                continue
            template_entry = self.session.resources.state_templates.get(state)
            if template_entry is None:
                continue
            template_paths = (
                template_entry if isinstance(template_entry, tuple) else (template_entry,)
            )
            for template_path in template_paths:
                if self.session.recognizer.match(template_path, screen):
                    return True
        return False
