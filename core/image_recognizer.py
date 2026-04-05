"""图像识别层，负责模板匹配。"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

log = logging.getLogger("core.image_recognizer")


@dataclass(frozen=True)
class TemplateMatchResult:
    """描述一次模板匹配的分数和命中坐标。"""

    score: float
    position: Optional[tuple[int, int]]


class ImageRecognizer:
    def __init__(self, threshold: float = 0.75) -> None:
        """初始化识别器，并设置默认匹配阈值。"""
        self.threshold = threshold
        self._template_cache: dict[str, np.ndarray] = {}
        self._screen_cache: dict[str, np.ndarray] = {}

    def _load_grayscale(
        self,
        image_path: str,
        *,
        use_cache: bool,
    ) -> Optional[np.ndarray]:
        """读取灰度图，并在允许时复用缓存内容。"""
        cache = self._template_cache if use_cache else self._screen_cache
        if image_path in cache:
            return cache[image_path]

        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            return None

        cache[image_path] = image
        return image

    def invalidate_screen_cache(self, screen_path: Optional[str] = None) -> None:
        """截图更新后清理旧的屏幕缓存。"""
        if screen_path is None:
            self._screen_cache.clear()
            return
        self._screen_cache.pop(screen_path, None)

    def match(
        self,
        template_path: str,
        screen: str | np.ndarray,
        threshold: Optional[float] = None,
        *,
        log_debug: bool = False,
    ) -> Optional[tuple[int, int]]:
        """在截图中查找模板，命中时返回模板中心点。"""
        result = self.match_with_score(
            template_path,
            screen,
            threshold,
            log_debug=log_debug,
        )
        return result.position

    def match_with_score(
        self,
        template_path: str,
        screen: str | np.ndarray,
        threshold: Optional[float] = None,
        *,
        log_debug: bool = False,
    ) -> TemplateMatchResult:
        """在截图中查找模板，并返回匹配分数和命中坐标。"""
        template = self._load_grayscale(template_path, use_cache=True)
        screen_image, screen_desc = self._load_screen(screen)

        if template is None:
            log.warning(f"模板图读取失败：{template_path}")
            return TemplateMatchResult(score=0.0, position=None)
        if screen_image is None:
            log.warning(f"截图读取失败：{screen_desc}")
            return TemplateMatchResult(score=0.0, position=None)

        return self.match_array_with_score(
            template=template,
            screen=screen_image,
            threshold=threshold,
            label=Path(template_path).name,
            log_debug=log_debug,
        )

    def match_array_with_score(
        self,
        template: np.ndarray,
        screen: str | np.ndarray,
        threshold: Optional[float] = None,
        *,
        mask: Optional[np.ndarray] = None,
        label: str = "<array>",
        log_debug: bool = False,
    ) -> TemplateMatchResult:
        """在截图中查找内存模板，并返回匹配分数和命中坐标。"""
        screen_image, screen_desc = self._load_screen(screen)
        if screen_image is None:
            log.warning(f"截图读取失败：{screen_desc}")
            return TemplateMatchResult(score=0.0, position=None)

        # 模板尺寸异常时直接跳过，避免 OpenCV 在匹配阶段报错。
        if (
            template.shape[0] > screen_image.shape[0]
            or template.shape[1] > screen_image.shape[1]
        ):
            log.warning(f"模板尺寸超过截图，跳过：{label}")
            return TemplateMatchResult(score=0.0, position=None)

        method = cv2.TM_CCORR_NORMED if mask is not None else cv2.TM_CCOEFF_NORMED
        if mask is not None:
            result = cv2.matchTemplate(screen_image, template, method, mask=mask)
        else:
            result = cv2.matchTemplate(screen_image, template, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        thr = threshold if threshold is not None else self.threshold
        if max_val >= thr:
            h, w = template.shape
            cx, cy = max_loc[0] + w // 2, max_loc[1] + h // 2
            if log_debug:
                log.debug(f"匹配成功 [{max_val:.2f}] {label} → ({cx}, {cy})")
            return TemplateMatchResult(score=float(max_val), position=(cx, cy))

        if log_debug:
            log.debug(f"匹配失败 [{max_val:.2f}] {label}")
        return TemplateMatchResult(score=float(max_val), position=None)

    def _load_screen(
        self, screen: str | np.ndarray
    ) -> tuple[Optional[np.ndarray], str]:
        if isinstance(screen, str):
            return self._load_grayscale(screen, use_cache=False), screen
        return screen, "<memory>"

    def match_multi(
        self,
        template_paths: list[str],
        screen: str | np.ndarray,
    ) -> Optional[tuple[str, tuple[int, int]]]:
        """按顺序尝试多个模板，返回首个命中的模板与坐标。"""
        for tmpl in template_paths:
            pos = self.match(tmpl, screen)
            if pos:
                return tmpl, pos
        return None

    def wait_for(
        self,
        template_path: str,
        screen_callback: Callable[[], str],
        timeout: float = 30.0,
        interval: float = 1.0,
    ) -> Optional[tuple[int, int]]:
        """轮询截图，直到指定模板出现或超时。"""
        deadline = time.time() + timeout
        attempts = 0
        while time.time() < deadline:
            screen_path = screen_callback()
            pos = self.match(template_path, screen_path)
            if pos:
                log.debug(f"等待成功（{attempts + 1} 次）：{Path(template_path).name}")
                return pos
            attempts += 1
            time.sleep(interval)

        log.warning(
            f"等待超时 {timeout}s（尝试 {attempts} 次）：{Path(template_path).name}"
        )
        return None

    def wait_for_any(
        self,
        template_paths: list[str],
        screen_callback: Callable[[], str],
        timeout: float = 30.0,
        interval: float = 1.0,
    ) -> Optional[tuple[str, tuple[int, int]]]:
        """轮询截图，直到多个模板中的任意一个出现。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            screen_path = screen_callback()
            result = self.match_multi(template_paths, screen_path)
            if result:
                return result
            time.sleep(interval)

        log.warning(f"等待超时 {timeout}s，模板均未出现：{template_paths}")
        return None

