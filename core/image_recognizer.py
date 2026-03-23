"""
core/image_recognizer.py

职责：图像识别（只读屏幕，不操作设备）
包含：
  - match()          单模板匹配，返回中心坐标
  - match_multi()    多模板同时匹配，返回第一个命中的
  - wait_for()       阻塞等待某模板出现
  - is_skill_ready() 亮度检测判断技能是否冷却
"""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

log = logging.getLogger("core.image_recognizer")


class ImageRecognizer:
    def __init__(self, threshold: float = 0.75) -> None:
        """
        threshold: 模板匹配置信度阈值（0~1）
                   从 BattleConfig 传入，保持全局一致
        """
        self.threshold = threshold

    # ── 核心匹配 ──────────────────────────────
    def match(
        self,
        template_path: str,
        screen_path: str,
        threshold: Optional[float] = None,  # 单次覆盖全局阈值
    ) -> Optional[tuple[int, int]]:
        """
        在屏幕截图中查找模板，返回匹配区域的中心坐标。
        未找到返回 None。

        示例：
            pos = recognizer.match("assets/ui/skip.png", "screenshots/screen.png")
            if pos:
                adb.click_raw(*pos)
        """
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        screen = cv2.imread(screen_path, cv2.IMREAD_GRAYSCALE)

        if template is None:
            log.warning(f"模板图读取失败：{template_path}")
            return None
        if screen is None:
            log.warning(f"截图读取失败：{screen_path}")
            return None

        # 模板比屏幕大时直接跳过（防止 cv2 报错）
        if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
            log.warning(f"模板尺寸超过截图，跳过：{Path(template_path).name}")
            return None

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
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

    # ── 多模板匹配 ────────────────────────────
    def match_multi(
        self,
        template_paths: list[str],
        screen_path: str,
    ) -> Optional[tuple[str, tuple[int, int]]]:
        """
        同时尝试多个模板，返回第一个匹配成功的 (模板路径, 坐标)。
        用于状态检测：一次截图，同时判断多个可能的状态。

        示例：
            result = recognizer.match_multi(
                ["assets/ui/skip.png", "assets/ui/result.png"],
                screen_path
            )
            if result:
                tmpl, pos = result
        """
        for tmpl in template_paths:
            pos = self.match(tmpl, screen_path)
            if pos:
                return tmpl, pos
        return None

    # ── 等待模板出现 ──────────────────────────
    def wait_for(
        self,
        template_path: str,
        screen_callback: Callable[[], str],  # 无参函数，刷新截图并返回路径
        timeout: float = 30.0,
        interval: float = 1.0,
    ) -> Optional[tuple[int, int]]:
        """
        阻塞等待模板出现，适合已知"下一步会发生什么"的场景。
        比轮询 _detect_state() 更高效，动画播放期间不会产生无效识别。

        示例：
            # 点击 Attack 后，等待选卡界面出现
            battle.attack()
            pos = recognizer.wait_for(
                "assets/ui/attack_ready.png",
                lambda: adb.screenshot("screenshots/screen.png"),
                timeout=20.0,
            )
        """
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
        """
        等待多个模板中任意一个出现。
        用于不确定下一步是哪个状态时（比如战斗结束可能出现结算或剧情对话）。

        示例：
            result = recognizer.wait_for_any(
                ["assets/ui/result.png", "assets/ui/skip.png"],
                lambda: adb.screenshot("screenshots/screen.png"),
            )
            if result:
                tmpl, pos = result
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            screen_path = screen_callback()
            result = self.match_multi(template_paths, screen_path)
            if result:
                return result
            time.sleep(interval)

        log.warning(f"等待超时 {timeout}s，模板均未出现：{template_paths}")
        return None

    # ── 技能冷却检测 ──────────────────────────
    def is_skill_ready(
        self,
        screen_path: str,
        region: tuple[int, int, int, int],
        brightness_threshold: float = 80.0,
    ) -> bool:
        """
        通过区域平均亮度判断技能是否可用。
        冷却中的技能图标会变暗（灰色蒙版），亮度明显低于正常状态。

        region: (x1, y1, x2, y2) 技能图标区域，来自 GameCoordinates
        brightness_threshold: 低于此值视为冷却中，需根据实际截图校准

        示例：
            region = GameCoordinates.SERVANT_SKILL_REGIONS["s1_1"]
            if recognizer.is_skill_ready(screen_path, region):
                battle.use_servant_skill(1)
            else:
                log.info("技能1 冷却中，跳过")
        """
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
