"""状态识别层，负责把截图转换成流程可消费的 `GameState`。"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np

from core.shared.game_types import GameState
from core.perception.image_recognizer import ImageRecognizer
from core.shared.resource_catalog import ResourceCatalog

log = logging.getLogger("core.perception.state_detector")


@dataclass(frozen=True)
class StateDetectionResult:
    """描述一次状态检测的完整结果。"""

    state: GameState
    screen_path: str
    elapsed: float
    best_match_state: Optional[GameState] = None
    best_score: float = 0.0
    matched_template: Optional[str] = None
    missing_templates: list[str] = field(default_factory=list)


class StateDetector:
    """根据模板命中结果判断当前界面状态。"""

    def __init__(
        self,
        recognizer: ImageRecognizer,
        screen_callback: Callable[[], str],
        resources: ResourceCatalog,
        screen_array_callback: Optional[Callable[[], np.ndarray]] = None,
    ) -> None:
        self.recognizer = recognizer
        self.screen_callback = screen_callback
        self.screen_array_callback = screen_array_callback
        self.resources = resources

    def detect(
        self,
        *,
        candidates: Optional[Iterable[GameState]] = None,
    ) -> StateDetectionResult:
        """刷新截图并返回当前识别到的状态。"""
        started_at = time.perf_counter()
        screen_path = self.screen_callback()
        screen_image: str | np.ndarray = screen_path
        if self.screen_array_callback is not None:
            screen_image = self.screen_array_callback()
        detection_result = self._detect_from_states(
            screen_path=screen_path,
            screen_image=screen_image,
            states=candidates,
            started_at=started_at,
            allow_unknown=False,
        )
        if detection_result is not None:
            return detection_result
        return self._detect_from_states(
            screen_path=screen_path,
            screen_image=screen_image,
            states=None,
            started_at=started_at,
            allow_unknown=True,
        )

    def _detect_from_states(
        self,
        *,
        screen_path: str,
        screen_image: str | np.ndarray,
        states: Optional[Iterable[GameState]],
        started_at: float,
        allow_unknown: bool,
    ) -> Optional[StateDetectionResult]:
        best_match_state: Optional[GameState] = None
        best_score = 0.0
        best_template: Optional[str] = None
        matched_state: Optional[GameState] = None
        matched_score = 0.0
        matched_template: Optional[str] = None
        missing_templates: list[str] = []
        state_entries = self._resolve_state_entries(states)
        for state, template_entry in state_entries:
            template_paths = (
                list(template_entry)
                if isinstance(template_entry, tuple)
                else [template_entry]
            )
            for template_path in template_paths:
                if not Path(template_path).exists():
                    missing_templates.append(template_path)
                    continue

                match_result = self.recognizer.match_with_score(
                    template_path, screen_image
                )
                if match_result.score > best_score:
                    best_match_state = state
                    best_score = match_result.score
                    best_template = template_path

                if match_result.position and match_result.score > matched_score:
                    matched_state = state
                    matched_score = match_result.score
                    matched_template = template_path

        if matched_state is not None:
            elapsed = time.perf_counter() - started_at
            log.debug(
                "state detect matched %s score=%.2f template=%s in %.2fs",
                matched_state.name,
                matched_score,
                matched_template,
                elapsed,
            )
            return StateDetectionResult(
                state=matched_state,
                screen_path=screen_path,
                elapsed=elapsed,
                best_match_state=matched_state,
                best_score=matched_score,
                matched_template=matched_template,
                missing_templates=missing_templates,
            )

        if not allow_unknown:
            return None

        elapsed = time.perf_counter() - started_at
        if best_match_state is not None:
            log.debug(
                "state detect returned UNKNOWN best=%s score=%.2f template=%s in %.2fs",
                best_match_state.name,
                best_score,
                best_template,
                elapsed,
            )
        else:
            log.debug(f"state detect returned UNKNOWN in {elapsed:.2f}s")
        return StateDetectionResult(
            state=GameState.UNKNOWN,
            screen_path=screen_path,
            elapsed=elapsed,
            best_match_state=best_match_state,
            best_score=best_score,
            matched_template=best_template,
            missing_templates=missing_templates,
        )

    def _resolve_state_entries(
        self,
        states: Optional[Iterable[GameState]],
    ) -> list[tuple[GameState, str | tuple[str, ...]]]:
        if states is None:
            return list(self.resources.state_templates.items())
        entries: list[tuple[GameState, str | tuple[str, ...]]] = []
        seen: set[GameState] = set()
        for state in states:
            if state in seen:
                continue
            template_entry = self.resources.state_templates.get(state)
            if template_entry is None:
                continue
            entries.append((state, template_entry))
            seen.add(state)
        return entries
