"""普通指令卡局部特征编码。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from core.command_card_recognition.parts import CommandCardPartObservation
from core.support_recognition import PortraitEncoder


@dataclass(frozen=True)
class QueryPartFeatures:
    """描述单个 patch 的查询特征。"""

    embedding: np.ndarray
    gray_vector: np.ndarray
    edge_vector: np.ndarray


def normalize_feature_vector(values: np.ndarray) -> np.ndarray:
    vector = values.astype(np.float32, copy=False).reshape(-1)
    if vector.size == 0:
        return np.empty((0,), dtype=np.float32)
    vector = vector - float(vector.mean())
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-6:
        return np.zeros_like(vector, dtype=np.float32)
    return vector / norm


def gray_vector(image_rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    return normalize_feature_vector(gray)


def edge_vector(image_rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 64, 160)
    return normalize_feature_vector(edges)


def normalized_similarity(query: np.ndarray, bank: np.ndarray) -> np.ndarray:
    if query.size == 0 or bank.size == 0:
        return np.empty((0,), dtype=np.float32)
    return bank @ query.astype(np.float32, copy=False)


class PartFeatureEncoder:
    """将普通卡 patch 编码成 embedding 与局部验证向量。"""

    def __init__(self, encoder: PortraitEncoder) -> None:
        self.encoder = encoder

    def encode_query(self, part: CommandCardPartObservation) -> QueryPartFeatures:
        return QueryPartFeatures(
            embedding=self.encoder.encode(part.image_rgb),
            gray_vector=gray_vector(part.image_rgb),
            edge_vector=edge_vector(part.image_rgb),
        )
