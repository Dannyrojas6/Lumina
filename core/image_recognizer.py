"""图像识别层，负责模板匹配和简单亮度判断。"""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

log = logging.getLogger("core.image_recognizer")


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
    ) -> Optional[tuple[int, int]]:
        """在截图中查找模板，命中时返回模板中心点。"""
        template = self._load_grayscale(template_path, use_cache=True)
        if isinstance(screen, str):
            screen_image = self._load_grayscale(screen, use_cache=False)
            screen_desc = screen
        else:
            screen_image = screen
            screen_desc = "<memory>"

        if template is None:
            log.warning(f"模板图读取失败：{template_path}")
            return None
        if screen_image is None:
            log.warning(f"截图读取失败：{screen_desc}")
            return None

        # 模板尺寸异常时直接跳过，避免 OpenCV 在匹配阶段报错。
        if (
            template.shape[0] > screen_image.shape[0]
            or template.shape[1] > screen_image.shape[1]
        ):
            log.warning(f"模板尺寸超过截图，跳过：{Path(template_path).name}")
            return None

        result = cv2.matchTemplate(screen_image, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        thr = threshold if threshold is not None else self.threshold
        if max_val >= thr:
            h, w = template.shape
            cx, cy = max_loc[0] + w // 2, max_loc[1] + h // 2
            log.debug(
                f"匹配成功 [{max_val:.2f}] {Path(template_path).name} → ({cx}, {cy})"
            )
            return cx, cy

        log.debug(f"匹配失败 [{max_val:.2f}] {Path(template_path).name}")
        return None

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

    def is_skill_ready(
        self,
        screen_path: str,
        region: tuple[int, int, int, int],
        brightness_threshold: float = 80.0,
    ) -> bool:
        """通过区域平均亮度粗略判断技能是否处于可点击状态。"""
        img = cv2.imread(screen_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            log.warning(f"亮度检测：截图读取失败 {screen_path}")
            return False

        x1, y1, x2, y2 = region
        roi = img[y1:y2, x1:x2]

        if roi.size == 0:
            log.warning(f"亮度检测：区域为空 {region}")
            return False

        mean_brightness = float(np.mean(roi))
        is_ready = mean_brightness > brightness_threshold
        log.debug(
            f"技能亮度：{mean_brightness:.1f}  "
            f"阈值：{brightness_threshold}  "
            f"状态：{'可用' if is_ready else '冷却'}"
        )
        return is_ready
