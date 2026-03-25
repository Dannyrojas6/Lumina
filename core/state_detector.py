"""状态识别层，负责把截图转换成流程可消费的 `GameState`。"""

import logging
import time
from typing import Callable, Optional
from pathlib import Path

import numpy as np

from core.game_state import GameState
from core.image_recognizer import ImageRecognizer
from core.resources import ResourceCatalog

log = logging.getLogger("core.state_detector")


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

    def detect(self) -> tuple[GameState, str]:
        """刷新截图并返回当前识别到的状态。"""
        started_at = time.perf_counter()
        screen_path = self.screen_callback()
        screen_image: str | np.ndarray = screen_path
        if self.screen_array_callback is not None:
            screen_image = self.screen_array_callback()
        for state, template_path in self.resources.state_templates.items():
            if Path(template_path).exists() and self.recognizer.match(
                template_path, screen_image
            ):
                elapsed = time.perf_counter() - started_at
                log.debug(f"state detect matched {state.name} in {elapsed:.2f}s")
                return state, screen_path
        elapsed = time.perf_counter() - started_at
        log.debug(f"state detect returned UNKNOWN in {elapsed:.2f}s")
        return GameState.UNKNOWN, screen_path
