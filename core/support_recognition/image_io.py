"""助战识别图像读写。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


def load_rgb_image(image_path: str | Path) -> np.ndarray:
    """读取 RGB 图片，兼容中文路径。"""
    image = read_image(image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"无法读取图片：{image_path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def load_rgba_image(image_path: str | Path) -> np.ndarray:
    """读取 RGBA 图片，兼容中文路径。"""
    image = read_image(image_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"无法读取图片：{image_path}")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGBA)
    if image.shape[2] == 3:
        bgr = image
        alpha = np.full(bgr.shape[:2], 255, dtype=np.uint8)
        rgba = np.dstack([cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), alpha])
        return rgba
    return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)


def rgba_to_rgb_on_black(image_rgba: np.ndarray) -> np.ndarray:
    """将 atlas 透明底头像转成黑底 RGB。"""
    rgb = image_rgba[:, :, :3].astype(np.float32)
    alpha = image_rgba[:, :, 3:4].astype(np.float32) / 255.0
    blended = np.clip(rgb * alpha, 0, 255).astype(np.uint8)
    return blended


def write_png(path: str | Path, image: np.ndarray) -> None:
    """写入 PNG，兼容中文路径。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = image
    if image.ndim == 3 and image.shape[2] == 3:
        payload = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    encoded, buffer = cv2.imencode(".png", payload)
    if not encoded:
        raise RuntimeError(f"无法写入图片：{target}")
    buffer.tofile(target)


def read_image(image_path: str | Path, flags: int) -> Optional[np.ndarray]:
    """读取图片，兼容中文路径。"""
    raw = np.fromfile(str(image_path), dtype=np.uint8)
    if raw.size == 0:
        return None
    return cv2.imdecode(raw, flags)
