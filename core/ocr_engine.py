"""OCR 识别层，负责小区域文本读取与数字解析。"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger("core.ocr_engine")
_DLL_HANDLES: list[object] = []


@dataclass(frozen=True)
class OcrReadResult:
    """描述一次 OCR 读取的文本、数值和可信度。"""

    text: str
    value: Optional[int]
    confidence: float
    success: bool


@dataclass(frozen=True)
class OcrTextChunk:
    """描述 OCR 返回的单个文本块。"""

    text: str
    confidence: float
    left_x: float
    box: tuple[tuple[float, float], ...]


class PaddleOcrBackend:
    """基于 PaddleOCR 的默认后端实现。"""

    def __init__(self) -> None:
        self._ensure_torch_dll_path()
        try:
            import torch  # noqa: F401
        except ImportError as exc:  # pragma: no cover - 依赖安装后再验证
            raise RuntimeError("未安装 torch，无法启用 PaddleOCR 对照后端。") from exc
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover - 依赖安装后再验证
            raise RuntimeError("未安装 paddleocr，无法启用 PaddleOCR。") from exc

        self._engine = PaddleOCR(
            use_angle_cls=False,
            lang="ch",
            show_log=False,
            use_gpu=False,
            ir_optim=False,
            enable_mkldnn=False,
            cpu_threads=1,
        )

    def _ensure_torch_dll_path(self) -> None:
        if sys.platform != "win32":
            return
        torch_lib = Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib"
        if torch_lib.exists():
            _DLL_HANDLES.append(os.add_dll_directory(str(torch_lib)))

    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        chunks = self.recognize_chunks(image)
        if not chunks:
            return "", 0.0

        ordered_chunks = sorted(chunks, key=lambda item: item.left_x)
        texts = [item.text for item in ordered_chunks if item.text]
        scores = [item.confidence for item in ordered_chunks]
        return "".join(texts).strip(), max(scores) if scores else 0.0

    def recognize_chunks(self, image: np.ndarray) -> list[OcrTextChunk]:
        raw_output = self._engine.ocr(image, det=False, rec=True, cls=False)
        if not raw_output or not raw_output[0]:
            return []

        chunks: list[OcrTextChunk] = []
        for index, item in enumerate(raw_output[0]):
            text, confidence, left_x, box = self._parse_rec_item(
                item,
                fallback_index=index,
            )
            if text is None:
                continue
            chunks.append(
                OcrTextChunk(
                    text=text,
                    confidence=confidence,
                    left_x=left_x,
                    box=box,
                )
            )
        return chunks

    def _parse_rec_item(
        self,
        item,
        *,
        fallback_index: int,
    ) -> tuple[Optional[str], float, float, tuple[tuple[float, float], ...]]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            return None, 0.0, float(fallback_index), tuple()

        try:
            text = str(item[0])
            confidence = float(item[1])
        except (TypeError, ValueError):
            return None, 0.0, float(fallback_index), tuple()
        return text, confidence, float(fallback_index), tuple()

    def _parse_result_item(
        self,
        item,
        *,
        fallback_index: int,
    ) -> tuple[Optional[str], float, float, tuple[tuple[float, float], ...]]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            return None, 0.0, float(fallback_index), tuple()

        box = self._normalize_box(item[0])
        rec = item[1]
        if not isinstance(rec, (list, tuple)) or len(rec) < 2:
            return None, 0.0, float(fallback_index), box
        try:
            text = str(rec[0])
            confidence = float(rec[1])
        except (TypeError, ValueError):
            return None, 0.0, float(fallback_index), box
        left_x = min((point[0] for point in box), default=float(fallback_index))
        return text, confidence, left_x, box

    def _normalize_box(self, box) -> tuple[tuple[float, float], ...]:
        if not isinstance(box, (list, tuple)):
            return tuple()
        normalized: list[tuple[float, float]] = []
        for point in box:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                try:
                    normalized.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError):
                    continue
        return tuple(normalized)


class OcrEngine:
    """对 OCR 后端做裁图预处理、留档和数字解析。"""

    MAX_DEBUG_CROPS = 9

    def __init__(
        self,
        backend: Optional[PaddleOcrBackend] = None,
        *,
        min_confidence: float = 0.8,
        save_debug_crops: bool = True,
        debug_dir: str = "assets/screenshots/ocr",
    ) -> None:
        self.backend = backend or PaddleOcrBackend()
        self.min_confidence = min_confidence
        self.save_debug_crops = save_debug_crops
        self.debug_dir = Path(debug_dir)

    def read_number(
        self,
        image: np.ndarray,
        *,
        label: str,
        preset: str = "default",
    ) -> OcrReadResult:
        """读取区域中的数字，低置信度或无法解析时视为失败。"""
        prepared = self._prepare_image(image, preset=preset)
        if self.save_debug_crops:
            self._save_debug_crop(prepared, label)

        text, confidence = self.backend.recognize(prepared)
        value = self._extract_number(text)
        success = bool(text) and value is not None and confidence >= self.min_confidence
        log.debug(
            "OCR 读取 label=%s text=%s value=%s confidence=%.2f success=%s",
            label,
            text,
            value,
            confidence,
            success,
        )
        return OcrReadResult(
            text=text,
            value=value if success else None,
            confidence=confidence,
            success=success,
        )

    def read_chunks(
        self,
        image: np.ndarray,
        *,
        label: str,
        preset: str = "default",
    ) -> list[OcrTextChunk]:
        """返回当前图片的 OCR 文本块详情。"""
        prepared = self._prepare_image(image, preset=preset)
        if self.save_debug_crops:
            self._save_debug_crop(prepared, label)
        return self.backend.recognize_chunks(prepared)

    def _prepare_image(self, image: np.ndarray, *, preset: str = "default") -> np.ndarray:
        if image.ndim == 3:
            grayscale = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            grayscale = image.copy()

        if preset == "skill_corner":
            return self._prepare_skill_corner_image(grayscale)

        if preset != "default":
            raise ValueError(f"不支持的 OCR 预处理模式：{preset}")

        # 小数字裁图在强二值化下容易直接丢字，这里优先保留灰度细节。
        if grayscale.shape[0] <= 40:
            return self._prepare_small_crop_image(grayscale)

        enlarged = cv2.resize(
            grayscale,
            None,
            fx=3.0,
            fy=3.0,
            interpolation=cv2.INTER_CUBIC,
        )
        blurred = cv2.GaussianBlur(enlarged, (3, 3), 0)
        _, thresholded = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        return thresholded

    def _prepare_small_crop_image(self, grayscale: np.ndarray) -> np.ndarray:
        padded = cv2.copyMakeBorder(
            grayscale,
            12,
            12,
            12,
            12,
            cv2.BORDER_REPLICATE,
        )
        return cv2.resize(
            padded,
            None,
            fx=8.0,
            fy=8.0,
            interpolation=cv2.INTER_CUBIC,
        )

    def _prepare_skill_corner_image(self, grayscale: np.ndarray) -> np.ndarray:
        # 技能角落数字更小，先做对比度拉伸，再放大保留描边。
        normalized = cv2.normalize(grayscale, None, 0, 255, cv2.NORM_MINMAX)
        padded = cv2.copyMakeBorder(
            normalized,
            14,
            14,
            14,
            14,
            cv2.BORDER_REPLICATE,
        )
        enlarged = cv2.resize(
            padded,
            None,
            fx=10.0,
            fy=10.0,
            interpolation=cv2.INTER_CUBIC,
        )
        return cv2.GaussianBlur(enlarged, (3, 3), 0)

    def _save_debug_crop(self, image: np.ndarray, label: str) -> None:
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        existing_files = sorted(self.debug_dir.glob("*.png"), key=lambda path: path.stat().st_mtime)
        while len(existing_files) >= self.MAX_DEBUG_CROPS:
            existing_files[0].unlink(missing_ok=True)
            existing_files.pop(0)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_path = self.debug_dir / f"{timestamp}_{label}.png"
        cv2.imwrite(str(save_path), image)

    def _extract_number(self, text: str) -> Optional[int]:
        digits = re.findall(r"\d+", text)
        if not digits:
            return None
        return int("".join(digits))
