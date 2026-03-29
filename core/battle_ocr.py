"""战斗 OCR 识别层，负责从战斗画面中读取 NP 和少量战斗文本。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from core.config import BattleOcrConfig
from core.coordinates import GameCoordinates
from core.ocr_engine import OcrEngine

log = logging.getLogger("core.battle_ocr")

BASE_SCREEN_SIZE = (1920, 1080)


@dataclass(frozen=True)
class ServantNpStatus:
    """描述单个从者当前的 NP 识别结果。"""

    servant_index: int
    raw_text: str
    np_value: Optional[int]
    confidence: float
    success: bool
    is_ready: bool


class BattleOcrReader:
    """统一读取战斗画面中的 OCR 信息。"""

    def __init__(
        self,
        ocr_engine: Optional[OcrEngine] = None,
        config: Optional[BattleOcrConfig] = None,
        debug_dir: Optional[str] = None,
    ) -> None:
        self.config = config or BattleOcrConfig()
        self.ocr_engine = ocr_engine or OcrEngine(
            backend_name=self.config.backend,
            min_confidence=self.config.min_confidence,
            save_debug_crops=self.config.save_ocr_crops,
            debug_dir=debug_dir or "assets/screenshots/ocr",
        )

    def read_np_statuses(self, screen: np.ndarray) -> list[ServantNpStatus]:
        """读取三位从者的 NP 状态。"""
        statuses: list[ServantNpStatus] = []
        for servant_index, region in GameCoordinates.NP_TEXT_REGIONS.items():
            crop = self._crop_region(screen, region)
            result = self.read_number(crop, label=f"np_{servant_index}")
            np_value = result.value if result.success else None
            is_ready = bool(
                result.success
                and np_value is not None
                and np_value >= self.config.np_ready_value
            )
            statuses.append(
                ServantNpStatus(
                    servant_index=servant_index,
                    raw_text=result.text,
                    np_value=np_value,
                    confidence=result.confidence,
                    success=result.success,
                    is_ready=is_ready,
                )
            )
        return statuses

    def read_number(
        self,
        image: np.ndarray,
        *,
        label: str,
        preset: str = "default",
    ):
        """读取区域中的数字。"""
        return self.ocr_engine.read_number(image, label=label, preset=preset)

    def read_text(
        self,
        image: np.ndarray,
        *,
        label: str,
        preset: str = "default",
    ) -> tuple[str, float]:
        """读取区域中的原始文本，保留 OCR 结果供更高层解析。"""
        prepared = self.ocr_engine._prepare_image(image, preset=preset)
        if self.ocr_engine.save_debug_crops:
            self.ocr_engine._save_debug_crop(prepared, label)

        text, confidence = self.ocr_engine.backend.recognize(prepared)
        log.debug(
            "OCR 文本读取 label=%s text=%s confidence=%.2f",
            label,
            text,
            confidence,
        )
        return text, confidence

    def read_skill_corner_number(self, image: np.ndarray, *, label: str):
        """读取技能右下角冷却数字。"""
        return self.read_number(image, label=label, preset="skill_corner")

    def read_skill_corner_text(self, image: np.ndarray, *, label: str) -> tuple[str, float]:
        """读取技能左下角提示文本。"""
        return self.read_text(image, label=label, preset="skill_corner")

    def read_np_values(self, image_path: str | Path) -> list[int]:
        """供离线批量检查调用，返回三位从者的 NP 数值。"""
        raw_bytes = np.fromfile(str(image_path), dtype=np.uint8)
        if raw_bytes.size == 0:
            raise FileNotFoundError(f"无法读取截图：{image_path}")
        screen = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
        if screen is None:
            raise FileNotFoundError(f"无法读取截图：{image_path}")
        if (screen.shape[1], screen.shape[0]) != BASE_SCREEN_SIZE:
            screen = cv2.resize(screen, BASE_SCREEN_SIZE)
        screen_rgb = cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)
        statuses = self.read_np_statuses(screen_rgb)
        return [status.np_value if status.np_value is not None else -1 for status in statuses]

    def _crop_region(
        self,
        screen: np.ndarray,
        region: tuple[int, int, int, int],
    ) -> np.ndarray:
        x1, y1, x2, y2 = region
        return screen[y1:y2, x1:x2]
