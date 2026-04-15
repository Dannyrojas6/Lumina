"""普通指令卡裁图与基础观测。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.command_card_recognition.layout import (
    COMMAND_CARD_SLOT_LAYOUTS,
    crop_absolute_region,
)
from core.shared.screen_coordinates import GameCoordinates

SUPPORT_BADGE_ZONE_LEFT_RATIO = 0.48
SUPPORT_BADGE_ZONE_TOP_RATIO = 0.06
SUPPORT_BADGE_ZONE_RIGHT_RATIO = 0.98
SUPPORT_BADGE_ZONE_BOTTOM_RATIO = 0.28
SUPPORT_BADGE_MIN_WHITE_RATIO = 0.30
SUPPORT_BADGE_MIN_RED_RATIO = 0.045


@dataclass(frozen=True)
class CommandCardCrop:
    """描述单张普通卡的基础裁图结果。"""

    index: int
    full_card_rgb: np.ndarray
    recognition_rgb: np.ndarray
    color: str | None
    support_badge: bool
    crop_region_abs: tuple[int, int, int, int]


def crop_command_card_face(
    screen_rgb: np.ndarray,
    region: tuple[int, int, int, int],
) -> np.ndarray:
    x1, y1, x2, y2 = region
    midpoint = y1 + ((y2 - y1) // 2)
    return screen_rgb[y1:midpoint, x1:x2].copy()


def crop_command_card_color_zone(card_rgb: np.ndarray) -> np.ndarray:
    if card_rgb.size == 0:
        return card_rgb
    height, width = card_rgb.shape[:2]
    left_ratio, top_ratio, right_ratio, bottom_ratio = (
        GameCoordinates.COMMAND_CARD_COLOR_ZONE_RATIOS
    )
    x1 = max(0, min(int(round(width * left_ratio)), width))
    y1 = max(0, min(int(round(height * top_ratio)), height))
    x2 = max(x1, min(int(round(width * right_ratio)), width))
    y2 = max(y1, min(int(round(height * bottom_ratio)), height))
    return card_rgb[y1:y2, x1:x2].copy()


def detect_command_card_color(card_rgb: np.ndarray) -> str | None:
    sample = crop_command_card_color_zone(card_rgb)
    if sample.size == 0:
        return None
    mean_r, mean_g, mean_b = sample.reshape(-1, 3).mean(axis=0)
    if mean_b >= mean_g and mean_b >= mean_r:
        return "arts"
    if mean_g >= mean_r and mean_g >= mean_b:
        return "quick"
    return "buster"


def has_support_badge(card_rgb: np.ndarray) -> bool:
    if card_rgb.size == 0:
        return False
    height, width = card_rgb.shape[:2]
    x1 = max(0, min(int(round(width * SUPPORT_BADGE_ZONE_LEFT_RATIO)), width))
    y1 = max(0, min(int(round(height * SUPPORT_BADGE_ZONE_TOP_RATIO)), height))
    x2 = max(x1, min(int(round(width * SUPPORT_BADGE_ZONE_RIGHT_RATIO)), width))
    y2 = max(y1, min(int(round(height * SUPPORT_BADGE_ZONE_BOTTOM_RATIO)), height))
    zone = card_rgb[y1:y2, x1:x2]
    if zone.size == 0:
        return False

    flat = zone.reshape(-1, 3)
    white_ratio = np.mean(
        (flat[:, 0] > 205) & (flat[:, 1] > 205) & (flat[:, 2] > 205)
    )
    red_ratio = np.mean(
        (flat[:, 0] > 160) & (flat[:, 1] < 145) & (flat[:, 2] < 145)
    )
    return (
        float(white_ratio) >= SUPPORT_BADGE_MIN_WHITE_RATIO
        and float(red_ratio) >= SUPPORT_BADGE_MIN_RED_RATIO
    )


class CardCropper:
    """统一生成普通卡基础裁图。"""

    def crop(self, screen_rgb: np.ndarray, card_index: int) -> CommandCardCrop:
        full_region = GameCoordinates.COMMAND_CARD_REGIONS[card_index]
        slot_layout = COMMAND_CARD_SLOT_LAYOUTS[card_index]
        full_card_rgb = crop_absolute_region(screen_rgb, full_region)
        recognition_rgb = crop_absolute_region(screen_rgb, slot_layout.crop_region_abs)
        return CommandCardCrop(
            index=card_index,
            full_card_rgb=full_card_rgb,
            recognition_rgb=recognition_rgb,
            color=detect_command_card_color(full_card_rgb),
            support_badge=has_support_badge(full_card_rgb),
            crop_region_abs=slot_layout.crop_region_abs,
        )
