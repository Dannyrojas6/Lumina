"""普通指令卡识别区域布局。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CommandCardSlotLayout:
    """描述单个卡位用于人物识别的 crop 与遮挡。"""

    crop_region_abs: tuple[int, int, int, int]
    mask_rects: tuple[tuple[int, int, int, int], ...]

    @property
    def mask_rects_abs(self) -> list[tuple[int, int, int, int]]:
        x1, y1, _, _ = self.crop_region_abs
        return [
            (x1 + left, y1 + top, x1 + right, y1 + bottom)
            for left, top, right, bottom in self.mask_rects
        ]


@dataclass(frozen=True)
class CommandCardPartLayout:
    """描述普通卡局部区域的相对位置与基础权重。"""

    name: str
    bbox_ratio: tuple[float, float, float, float]
    base_weight: float


BASE_MASK_RECTS: tuple[tuple[int, int, int, int], ...] = (
    (0, 0, 232, 36),
    (0, 178, 232, 290),
)

COMMAND_CARD_SLOT_LAYOUTS: dict[int, CommandCardSlotLayout] = {
    1: CommandCardSlotLayout(
        (84, 617, 316, 907),
        BASE_MASK_RECTS,
    ),
    2: CommandCardSlotLayout(
        (464, 617, 696, 907),
        BASE_MASK_RECTS,
    ),
    3: CommandCardSlotLayout(
        (844, 615, 1076, 905),
        BASE_MASK_RECTS,
    ),
    4: CommandCardSlotLayout(
        (1231, 615, 1463, 905),
        BASE_MASK_RECTS,
    ),
    5: CommandCardSlotLayout(
        (1618, 615, 1850, 905),
        BASE_MASK_RECTS,
    ),
}

COMMAND_CARD_PART_LAYOUTS: tuple[CommandCardPartLayout, ...] = (
    CommandCardPartLayout(
        name="upper_face",
        bbox_ratio=(0.28, 0.14, 0.72, 0.32),
        base_weight=0.75,
    ),
    CommandCardPartLayout(
        name="center_face",
        bbox_ratio=(0.24, 0.22, 0.74, 0.44),
        base_weight=1.4,
    ),
    CommandCardPartLayout(
        name="left_silhouette",
        bbox_ratio=(0.16, 0.18, 0.44, 0.44),
        base_weight=0.7,
    ),
    CommandCardPartLayout(
        name="right_silhouette",
        bbox_ratio=(0.56, 0.18, 0.84, 0.44),
        base_weight=1.0,
    ),
    CommandCardPartLayout(
        name="upper_torso",
        bbox_ratio=(0.28, 0.34, 0.72, 0.50),
        base_weight=0.75,
    ),
)

COMMAND_CARD_PART_LAYOUTS_BY_SLOT: dict[int, tuple[CommandCardPartLayout, ...]] = {
    1: (
        CommandCardPartLayout(
            name="upper_face",
            bbox_ratio=(0.22, 0.14, 0.66, 0.32),
            base_weight=0.75,
        ),
        CommandCardPartLayout(
            name="center_face",
            bbox_ratio=(0.18, 0.22, 0.68, 0.44),
            base_weight=1.4,
        ),
        CommandCardPartLayout(
            name="left_silhouette",
            bbox_ratio=(0.10, 0.18, 0.38, 0.44),
            base_weight=0.7,
        ),
        CommandCardPartLayout(
            name="right_silhouette",
            bbox_ratio=(0.50, 0.18, 0.78, 0.44),
            base_weight=1.0,
        ),
        CommandCardPartLayout(
            name="upper_torso",
            bbox_ratio=(0.22, 0.34, 0.66, 0.50),
            base_weight=0.75,
        ),
    ),
    2: COMMAND_CARD_PART_LAYOUTS,
    3: COMMAND_CARD_PART_LAYOUTS,
    4: COMMAND_CARD_PART_LAYOUTS,
    5: COMMAND_CARD_PART_LAYOUTS,
}


COMMAND_CARD_PART_LAYOUTS_BY_SLOT_AND_COLOR: dict[
    tuple[int, str], tuple[CommandCardPartLayout, ...]
] = {
    (2, "quick"): (
        CommandCardPartLayout(
            name="upper_face",
            bbox_ratio=(0.28, 0.14, 0.72, 0.32),
            base_weight=0.6,
        ),
        CommandCardPartLayout(
            name="center_face",
            bbox_ratio=(0.24, 0.22, 0.74, 0.44),
            base_weight=1.9,
        ),
        CommandCardPartLayout(
            name="left_silhouette",
            bbox_ratio=(0.16, 0.18, 0.44, 0.44),
            base_weight=0.55,
        ),
        CommandCardPartLayout(
            name="right_silhouette",
            bbox_ratio=(0.56, 0.18, 0.84, 0.44),
            base_weight=0.25,
        ),
        CommandCardPartLayout(
            name="upper_torso",
            bbox_ratio=(0.28, 0.34, 0.72, 0.50),
            base_weight=1.15,
        ),
    ),
}


def part_layouts_for_slot(
    card_index: int,
    card_color: str | None = None,
) -> tuple[CommandCardPartLayout, ...]:
    if card_color:
        color_specific = COMMAND_CARD_PART_LAYOUTS_BY_SLOT_AND_COLOR.get(
            (card_index, card_color)
        )
        if color_specific is not None:
            return color_specific
    return COMMAND_CARD_PART_LAYOUTS_BY_SLOT.get(card_index, COMMAND_CARD_PART_LAYOUTS)

SUPPORT_BADGE_MASK_RATIO: tuple[float, float, float, float] = (0.46, 0.02, 0.98, 0.27)


def crop_absolute_region(
    image_rgb: np.ndarray,
    region: tuple[int, int, int, int],
) -> np.ndarray:
    x1, y1, x2, y2 = region
    return image_rgb[y1:y2, x1:x2].copy()


def apply_local_masks(
    image_rgb: np.ndarray,
    mask_rects: tuple[tuple[int, int, int, int], ...],
) -> np.ndarray:
    if image_rgb.size == 0 or not mask_rects:
        return image_rgb.copy()

    masked = image_rgb.copy()
    height, width = masked.shape[:2]
    mask_map = np.zeros((height, width), dtype=bool)
    for x1, y1, x2, y2 in mask_rects:
        left = min(max(x1, 0), width)
        top = min(max(y1, 0), height)
        right = min(max(x2, 0), width)
        bottom = min(max(y2, 0), height)
        if right > left and bottom > top:
            mask_map[top:bottom, left:right] = True

    if not np.any(mask_map):
        return masked

    keep_mask = ~mask_map
    if np.any(keep_mask):
        fill = np.round(masked[keep_mask].reshape(-1, 3).mean(axis=0)).astype(np.uint8)
    else:
        fill = np.zeros(3, dtype=np.uint8)
    masked[mask_map] = fill
    return masked


def crop_command_card_for_recognition(
    screen_rgb: np.ndarray,
    card_index: int,
) -> np.ndarray:
    layout = COMMAND_CARD_SLOT_LAYOUTS[card_index]
    cropped = crop_absolute_region(screen_rgb, layout.crop_region_abs)
    return apply_local_masks(cropped, layout.mask_rects)
