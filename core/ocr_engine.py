"""OCR 识别层，负责小区域文本读取与数字解析。"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

import cv2
import numpy as np

log = logging.getLogger("core.ocr_engine")


@dataclass(frozen=True)
class OcrReadResult:
    """描述一次 OCR 读取的文本、数值和可信度。"""

    text: str
    value: Optional[int]
    confidence: float
    success: bool


class OcrBackend(Protocol):
    """描述 OCR 后端的最小接口。"""

    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        """返回识别文本和综合置信度。"""


class RapidOcrBackend:
    """基于 RapidOCR 的默认后端实现。"""

    def __init__(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:  # pragma: no cover - 依赖安装后再验证
            raise RuntimeError(
                "未安装 rapidocr-onnxruntime，无法启用 OCR。"
            ) from exc

        self._engine = RapidOCR()

    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        raw_output = self._engine(image)
        results = self._extract_results(raw_output)
        if not results:
            return "", 0.0

        texts = [text for text, _ in results if text]
        scores = [score for _, score in results]
        merged_text = "".join(texts).strip()
        confidence = max(scores) if scores else 0.0
        return merged_text, confidence

    def _extract_results(self, raw_output) -> list[tuple[str, float]]:
        if raw_output is None:
            return []

        if isinstance(raw_output, tuple):
            raw_output = raw_output[0]

        results: list[tuple[str, float]] = []
        if not isinstance(raw_output, list):
            return results

        for item in raw_output:
            text, confidence = self._parse_result_item(item)
            if text is None:
                continue
            results.append((text, confidence))
        return results

    def _parse_result_item(self, item) -> tuple[Optional[str], float]:
        if not isinstance(item, (list, tuple)):
            return None, 0.0

        if len(item) >= 3:
            return str(item[1]), float(item[2])

        if len(item) == 2 and isinstance(item[1], (list, tuple)) and len(item[1]) >= 2:
            return str(item[1][0]), float(item[1][1])

        return None, 0.0


class OcrEngine:
    """对 OCR 后端做裁图预处理、留档和数字解析。"""

    MAX_DEBUG_CROPS = 9

    def __init__(
        self,
        backend: Optional[OcrBackend] = None,
        *,
        backend_name: str = "rapidocr",
        min_confidence: float = 0.8,
        save_debug_crops: bool = True,
        debug_dir: str = "assets/screenshots/ocr",
    ) -> None:
        self.backend = backend or self._build_backend(backend_name)
        self.min_confidence = min_confidence
        self.save_debug_crops = save_debug_crops
        self.debug_dir = Path(debug_dir)

    def read_number(self, image: np.ndarray, *, label: str) -> OcrReadResult:
        """读取区域中的数字，低置信度或无法解析时视为失败。"""
        prepared = self._prepare_image(image)
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

    def _prepare_image(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 3:
            grayscale = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            grayscale = image.copy()

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

    def _build_backend(self, backend_name: str) -> OcrBackend:
        normalized = backend_name.strip().lower()
        if normalized == "rapidocr":
            return RapidOcrBackend()
        raise ValueError(f"不支持的 OCR 后端：{backend_name}")
