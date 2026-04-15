"""普通指令卡局部区域提取。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from core.command_card_recognition.layout import part_layouts_for_slot

MIN_VISIBLE_RATIO = 0.35


@dataclass(frozen=True)
class CommandCardPartObservation:
    """描述单张卡单个局部区域的观测结果。"""

    part_name: str
    image_rgb: np.ndarray
    visible_ratio: float
    texture_score: float
    weight: float
    bbox_local: tuple[int, int, int, int]
    bbox_abs: tuple[int, int, int, int]
    valid: bool


class CardPartExtractor:
    """从遮挡后的普通卡中提取固定 patch。"""

    def extract(
        self,
        *,
        card_index: int,
        card_color: str | None,
        masked_rgb: np.ndarray,
        visibility_mask: np.ndarray,
        crop_region_abs: tuple[int, int, int, int],
    ) -> list[CommandCardPartObservation]:
        height, width = masked_rgb.shape[:2]
        crop_x1, crop_y1, _, _ = crop_region_abs
        observations: list[CommandCardPartObservation] = []
        for layout in part_layouts_for_slot(card_index, card_color):
            bbox_local = self._ratio_bbox_to_local(layout.bbox_ratio, width, height)
            x1, y1, x2, y2 = bbox_local
            patch_rgb = masked_rgb[y1:y2, x1:x2].copy()
            patch_visible = visibility_mask[y1:y2, x1:x2]
            visible_ratio = float(np.mean(patch_visible)) if patch_visible.size else 0.0
            texture_score = self._texture_score(patch_rgb, patch_visible)
            weight = float(layout.base_weight) * visible_ratio * max(texture_score, 0.1)
            observations.append(
                CommandCardPartObservation(
                    part_name=layout.name,
                    image_rgb=patch_rgb,
                    visible_ratio=visible_ratio,
                    texture_score=texture_score,
                    weight=weight,
                    bbox_local=bbox_local,
                    bbox_abs=(crop_x1 + x1, crop_y1 + y1, crop_x1 + x2, crop_y1 + y2),
                    valid=visible_ratio >= MIN_VISIBLE_RATIO and texture_score > 0.0,
                )
            )
        return observations

    def _ratio_bbox_to_local(
        self,
        bbox_ratio: tuple[float, float, float, float],
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        left_ratio, top_ratio, right_ratio, bottom_ratio = bbox_ratio
        x1 = max(0, min(int(round(width * left_ratio)), width))
        y1 = max(0, min(int(round(height * top_ratio)), height))
        x2 = max(x1 + 1, min(int(round(width * right_ratio)), width))
        y2 = max(y1 + 1, min(int(round(height * bottom_ratio)), height))
        return (x1, y1, x2, y2)

    def _texture_score(
        self,
        patch_rgb: np.ndarray,
        patch_visible: np.ndarray,
    ) -> float:
        if patch_rgb.size == 0 or patch_visible.size == 0 or not np.any(patch_visible):
            return 0.0
        gray = cv2.cvtColor(patch_rgb, cv2.COLOR_RGB2GRAY)
        visible_gray = gray[patch_visible]
        if visible_gray.size == 0:
            return 0.0
        std = float(np.std(visible_gray))
        return min(std / 64.0, 1.0)
