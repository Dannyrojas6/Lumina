"""助战头像向量库读写与元数据。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from core.support_recognition.masking import (
    DEFAULT_IGNORE_REGIONS,
    DEFAULT_MASK_BASE_SIZE,
    DEFAULT_MASKED_FACE_CROP,
    _masked_or_legacy,
)

DEFAULT_NEGATIVE_PENALTY = 0.85
DEFAULT_SQUARE_WEIGHT = 0.4
DEFAULT_FACE_WEIGHT = 0.6
DEFAULT_MIN_SCORE = 0.30
DEFAULT_MIN_MARGIN = 0.15


@dataclass(frozen=True)
class PortraitReferenceBank:
    """描述目标人物头像的正反例向量库。"""

    servant_name: str
    square_positive: np.ndarray
    face_positive: np.ndarray
    square_negative: np.ndarray
    face_negative: np.ndarray
    source_names: list[str]
    negative_names: list[str]
    masked_full_positive: Optional[np.ndarray] = None
    masked_face_positive: Optional[np.ndarray] = None
    masked_full_negative: Optional[np.ndarray] = None
    masked_face_negative: Optional[np.ndarray] = None


@dataclass(frozen=True)
class PortraitReferenceMeta:
    """描述向量库默认阈值与裁图规则。"""

    servant_name: str
    model_path: str
    image_size: int
    embedding_dim: int
    square_weight: float = DEFAULT_SQUARE_WEIGHT
    face_weight: float = DEFAULT_FACE_WEIGHT
    negative_penalty: float = DEFAULT_NEGATIVE_PENALTY
    min_score: float = DEFAULT_MIN_SCORE
    min_margin: float = DEFAULT_MIN_MARGIN
    portrait_crop: tuple[int, int, int, int] = (24, 18, 176, 170)
    face_crop: tuple[int, int, int, int] = (30, 18, 150, 128)
    base_size: tuple[int, int] = DEFAULT_MASK_BASE_SIZE
    ignore_regions: tuple[tuple[int, int, int, int], ...] = DEFAULT_IGNORE_REGIONS
    masked_face_crop: tuple[int, int, int, int] = DEFAULT_MASKED_FACE_CROP
    positive_samples: list[str] | None = None
    negative_samples: list[str] | None = None

    @classmethod
    def from_json(cls, path: Path) -> "PortraitReferenceMeta":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            servant_name=str(data["servant_name"]),
            model_path=str(data["model_path"]),
            image_size=int(data["image_size"]),
            embedding_dim=int(data["embedding_dim"]),
            square_weight=float(data.get("square_weight", DEFAULT_SQUARE_WEIGHT)),
            face_weight=float(data.get("face_weight", DEFAULT_FACE_WEIGHT)),
            negative_penalty=float(data.get("negative_penalty", DEFAULT_NEGATIVE_PENALTY)),
            min_score=float(data.get("min_score", DEFAULT_MIN_SCORE)),
            min_margin=float(data.get("min_margin", DEFAULT_MIN_MARGIN)),
            portrait_crop=tuple(int(item) for item in data["portrait_crop"]),
            face_crop=tuple(int(item) for item in data["face_crop"]),
            base_size=tuple(int(item) for item in data.get("base_size", list(DEFAULT_MASK_BASE_SIZE))),
            ignore_regions=tuple(
                tuple(int(value) for value in region)
                for region in data.get("ignore_regions", list(DEFAULT_IGNORE_REGIONS))
            ),
            masked_face_crop=tuple(
                int(item) for item in data.get("masked_face_crop", list(DEFAULT_MASKED_FACE_CROP))
            ),
            positive_samples=[str(item) for item in data.get("positive_samples", [])],
            negative_samples=[str(item) for item in data.get("negative_samples", [])],
        )

    def to_json(self, path: Path) -> None:
        payload = {
            "servant_name": self.servant_name,
            "model_path": self.model_path,
            "image_size": self.image_size,
            "embedding_dim": self.embedding_dim,
            "square_weight": self.square_weight,
            "face_weight": self.face_weight,
            "negative_penalty": self.negative_penalty,
            "min_score": self.min_score,
            "min_margin": self.min_margin,
            "portrait_crop": list(self.portrait_crop),
            "face_crop": list(self.face_crop),
            "base_size": list(self.base_size),
            "ignore_regions": [list(region) for region in self.ignore_regions],
            "masked_face_crop": list(self.masked_face_crop),
            "positive_samples": self.positive_samples or [],
            "negative_samples": self.negative_samples or [],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_reference_bank(path: str | Path) -> PortraitReferenceBank:
    """加载人物头像向量库。"""
    payload = np.load(Path(path), allow_pickle=False)
    square_positive = np.asarray(payload["square_positive"], dtype=np.float32)
    face_positive = np.asarray(payload["face_positive"], dtype=np.float32)
    square_negative = np.asarray(payload["square_negative"], dtype=np.float32)
    face_negative = np.asarray(payload["face_negative"], dtype=np.float32)
    return PortraitReferenceBank(
        servant_name=str(payload["servant_name"][0]),
        square_positive=square_positive,
        face_positive=face_positive,
        square_negative=square_negative,
        face_negative=face_negative,
        masked_full_positive=np.asarray(payload["masked_full_positive"], dtype=np.float32)
        if "masked_full_positive" in payload.files
        else square_positive,
        masked_face_positive=np.asarray(payload["masked_face_positive"], dtype=np.float32)
        if "masked_face_positive" in payload.files
        else face_positive,
        masked_full_negative=np.asarray(payload["masked_full_negative"], dtype=np.float32)
        if "masked_full_negative" in payload.files
        else square_negative,
        masked_face_negative=np.asarray(payload["masked_face_negative"], dtype=np.float32)
        if "masked_face_negative" in payload.files
        else face_negative,
        source_names=[str(item) for item in payload["source_names"].tolist()],
        negative_names=[str(item) for item in payload["negative_names"].tolist()],
    )


def save_reference_bank(path: str | Path, bank: PortraitReferenceBank) -> None:
    """写入人物头像向量库。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        target,
        servant_name=np.asarray([bank.servant_name]),
        square_positive=bank.square_positive.astype(np.float32),
        face_positive=bank.face_positive.astype(np.float32),
        square_negative=bank.square_negative.astype(np.float32),
        face_negative=bank.face_negative.astype(np.float32),
        masked_full_positive=_masked_or_legacy(bank.masked_full_positive, bank.square_positive).astype(np.float32),
        masked_face_positive=_masked_or_legacy(bank.masked_face_positive, bank.face_positive).astype(np.float32),
        masked_full_negative=_masked_or_legacy(bank.masked_full_negative, bank.square_negative).astype(np.float32),
        masked_face_negative=_masked_or_legacy(bank.masked_face_negative, bank.face_negative).astype(np.float32),
        source_names=np.asarray(bank.source_names),
        negative_names=np.asarray(bank.negative_names),
    )


def bank_counts(bank: PortraitReferenceBank) -> dict[str, int]:
    """返回向量库样本数量，便于调试输出。"""
    return {
        "square_positive": int(bank.square_positive.shape[0]),
        "face_positive": int(bank.face_positive.shape[0]),
        "square_negative": int(bank.square_negative.shape[0]),
        "face_negative": int(bank.face_negative.shape[0]),
        "masked_full_positive": int(_masked_or_legacy(bank.masked_full_positive, bank.square_positive).shape[0]),
        "masked_face_positive": int(_masked_or_legacy(bank.masked_face_positive, bank.face_positive).shape[0]),
        "masked_full_negative": int(_masked_or_legacy(bank.masked_full_negative, bank.square_negative).shape[0]),
        "masked_face_negative": int(_masked_or_legacy(bank.masked_face_negative, bank.face_negative).shape[0]),
    }


def meta_to_debug_dict(meta: PortraitReferenceMeta) -> dict[str, Any]:
    """返回简化后的元数据。"""
    return {
        "servant_name": meta.servant_name,
        "image_size": meta.image_size,
        "embedding_dim": meta.embedding_dim,
        "square_weight": meta.square_weight,
        "face_weight": meta.face_weight,
        "negative_penalty": meta.negative_penalty,
        "min_score": meta.min_score,
        "min_margin": meta.min_margin,
        "portrait_crop": list(meta.portrait_crop),
        "face_crop": list(meta.face_crop),
        "base_size": list(meta.base_size),
        "ignore_regions": [list(region) for region in meta.ignore_regions],
        "masked_face_crop": list(meta.masked_face_crop),
    }
