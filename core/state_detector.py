"""状态识别层，负责把截图转换成流程可消费的 `GameState`。"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from core.game_state import GameState
from core.image_recognizer import ImageRecognizer
from core.resources import ResourceCatalog

log = logging.getLogger("core.state_detector")


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

    def detect(self) -> StateDetectionResult:
        """刷新截图并返回当前识别到的状态。"""
        started_at = time.perf_counter()
        screen_path = self.screen_callback()
        screen_image: str | np.ndarray = screen_path
        if self.screen_array_callback is not None:
            screen_image = self.screen_array_callback()
        best_match_state: Optional[GameState] = None
        best_score = 0.0
        best_template: Optional[str] = None
        missing_templates: list[str] = []
        for state, template_path in self.resources.state_templates.items():
            if not Path(template_path).exists():
                missing_templates.append(template_path)
                continue

            match_result = self.recognizer.match_with_score(template_path, screen_image)
            if match_result.score > best_score:
                best_match_state = state
                best_score = match_result.score
                best_template = template_path
            if match_result.position:
                elapsed = time.perf_counter() - started_at
                log.debug(f"state detect matched {state.name} in {elapsed:.2f}s")
                return StateDetectionResult(
                    state=state,
                    screen_path=screen_path,
                    elapsed=elapsed,
                    best_match_state=state,
                    best_score=match_result.score,
                    matched_template=template_path,
                    missing_templates=missing_templates,
                )
        elapsed = time.perf_counter() - started_at
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
