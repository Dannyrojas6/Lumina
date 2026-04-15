"""普通指令卡固定遮挡建模。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.command_card_recognition.layout import (
    COMMAND_CARD_SLOT_LAYOUTS,
    SUPPORT_BADGE_MASK_RATIO,
    apply_local_masks,
)


@dataclass(frozen=True)
class OcclusionResult:
    """描述普通卡裁图的遮挡结果。"""

    masked_rgb: np.ndarray
    visibility_mask: np.ndarray
    mask_rects: tuple[tuple[int, int, int, int], ...]
    mask_rects_abs: list[tuple[int, int, int, int]]


def build_visibility_mask(
    shape: tuple[int, int],
    mask_rects: tuple[tuple[int, int, int, int], ...],
) -> np.ndarray:
    height, width = shape
    visible = np.ones((height, width), dtype=bool)
    for x1, y1, x2, y2 in mask_rects:
        left = min(max(x1, 0), width)
        top = min(max(y1, 0), height)
        right = min(max(x2, 0), width)
        bottom = min(max(y2, 0), height)
        if right > left and bottom > top:
            visible[top:bottom, left:right] = False
    return visible


class OcclusionMaskBuilder:
    """为普通卡生成固定版式遮挡。"""

    def build(
        self,
        card_rgb: np.ndarray,
        *,
        card_index: int,
        support_badge: bool,
    ) -> OcclusionResult:
        slot_layout = COMMAND_CARD_SLOT_LAYOUTS[card_index]
        mask_rects = list(slot_layout.mask_rects)
        if support_badge:
            mask_rects.append(
                self._ratio_rect_to_local(card_rgb.shape[1], card_rgb.shape[0])
            )
        mask_rects_tuple = tuple(mask_rects)
        masked_rgb = apply_local_masks(card_rgb, mask_rects_tuple)
        visibility_mask = build_visibility_mask(card_rgb.shape[:2], mask_rects_tuple)
        x1, y1, _, _ = slot_layout.crop_region_abs
        mask_rects_abs = [
            (x1 + left, y1 + top, x1 + right, y1 + bottom)
            for left, top, right, bottom in mask_rects_tuple
        ]
        return OcclusionResult(
            masked_rgb=masked_rgb,
            visibility_mask=visibility_mask,
            mask_rects=mask_rects_tuple,
            mask_rects_abs=mask_rects_abs,
        )

    def _ratio_rect_to_local(
        self,
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        left_ratio, top_ratio, right_ratio, bottom_ratio = SUPPORT_BADGE_MASK_RATIO
        return (
            max(0, min(int(round(width * left_ratio)), width)),
            max(0, min(int(round(height * top_ratio)), height)),
            max(0, min(int(round(width * right_ratio)), width)),
            max(0, min(int(round(height * bottom_ratio)), height)),
        )
