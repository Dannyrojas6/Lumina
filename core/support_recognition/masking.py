"""助战头像遮挡排除与裁图。"""

from __future__ import annotations

import cv2
import numpy as np

DEFAULT_MASK_BASE_SIZE = (240, 260)
DEFAULT_IGNORE_REGIONS = (
    (0, 190, 240, 260),
    (0, 0, 68, 66),
    (77, 13, 223, 43),
    (113, 148, 230, 186),
    (197, 113, 231, 146),
)
DEFAULT_MASKED_FACE_CROP = (57, 45, 195, 149)


def build_masked_portrait_views(
    image_rgb: np.ndarray,
    *,
    base_size: tuple[int, int] = DEFAULT_MASK_BASE_SIZE,
    ignore_regions: tuple[tuple[int, int, int, int], ...] = DEFAULT_IGNORE_REGIONS,
    masked_face_crop: tuple[int, int, int, int] = DEFAULT_MASKED_FACE_CROP,
) -> tuple[np.ndarray, np.ndarray]:
    """将头像统一到基准尺寸，并去掉固定遮挡区。"""
    base_image = _resize_to_base(image_rgb, base_size)
    masked_full = base_image.copy()
    valid_mask = np.ones(masked_full.shape[:2], dtype=bool)
    for region in ignore_regions:
        left, top, right, bottom = _clip_region(region, base_size)
        if right <= left or bottom <= top:
            continue
        valid_mask[top:bottom, left:right] = False
    _neutralize_ignored_pixels(masked_full, valid_mask)
    masked_face = _crop_base_region(masked_full, masked_face_crop, base_size)
    return masked_full, masked_face


def _masked_or_legacy(
    masked: np.ndarray | None,
    legacy: np.ndarray,
) -> np.ndarray:
    if masked is None:
        return legacy
    return masked


def _resize_to_base(
    image_rgb: np.ndarray,
    base_size: tuple[int, int],
) -> np.ndarray:
    target_width, target_height = base_size
    if image_rgb.size == 0:
        return np.zeros((target_height, target_width, 3), dtype=np.uint8)
    interpolation = (
        cv2.INTER_CUBIC
        if image_rgb.shape[1] < target_width or image_rgb.shape[0] < target_height
        else cv2.INTER_AREA
    )
    return cv2.resize(
        image_rgb,
        (target_width, target_height),
        interpolation=interpolation,
    )


def _clip_region(
    region: tuple[int, int, int, int],
    base_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    target_width, target_height = base_size
    x1, y1, x2, y2 = region
    left = max(0, min(x1, target_width))
    right = max(0, min(x2, target_width))
    top = max(0, min(y1, target_height))
    bottom = max(0, min(y2, target_height))
    return left, top, right, bottom


def _neutralize_ignored_pixels(image_rgb: np.ndarray, valid_mask: np.ndarray) -> None:
    if not np.any(valid_mask):
        image_rgb[:, :] = 0
        return
    mean_color = image_rgb[valid_mask].reshape(-1, 3).mean(axis=0)
    image_rgb[~valid_mask] = np.round(mean_color).astype(np.uint8)


def _crop_base_region(
    image_rgb: np.ndarray,
    region: tuple[int, int, int, int],
    base_size: tuple[int, int],
) -> np.ndarray:
    left, top, right, bottom = _clip_region(region, base_size)
    if right <= left or bottom <= top:
        return np.zeros((24, 24, 3), dtype=np.uint8)
    return image_rgb[top:bottom, left:right]
