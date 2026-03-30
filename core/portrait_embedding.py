"""人物头像向量编码与向量库读写。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
import onnx
import onnx.helper as oh
import onnxruntime as ort

INPUT_IMAGE_SIZE = 24
INPUT_VECTOR_LENGTH = INPUT_IMAGE_SIZE * INPUT_IMAGE_SIZE * 3
EMBEDDING_DIM = 128
PROJECTION_SEED = 7040
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
            negative_penalty=float(
                data.get("negative_penalty", DEFAULT_NEGATIVE_PENALTY)
            ),
            min_score=float(data.get("min_score", DEFAULT_MIN_SCORE)),
            min_margin=float(data.get("min_margin", DEFAULT_MIN_MARGIN)),
            portrait_crop=tuple(int(item) for item in data["portrait_crop"]),
            face_crop=tuple(int(item) for item in data["face_crop"]),
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
            "positive_samples": self.positive_samples or [],
            "negative_samples": self.negative_samples or [],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class PortraitEncoder:
    """使用 ONNX Runtime 将头像裁图编码为归一化向量。"""

    def __init__(self, model_path: str | Path) -> None:
        self.model_path = Path(model_path)
        ensure_portrait_encoder_model(self.model_path)
        self._session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name
        self._output_name = self._session.get_outputs()[0].name

    def encode(self, image_rgb: np.ndarray) -> np.ndarray:
        return self.encode_batch([image_rgb])[0]

    def encode_batch(self, images_rgb: list[np.ndarray]) -> np.ndarray:
        if not images_rgb:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        batch = np.stack([prepare_encoder_input(item) for item in images_rgb], axis=0)
        outputs = self._session.run(
            [self._output_name],
            {self._input_name: batch.astype(np.float32, copy=False)},
        )[0]
        return np.asarray(outputs, dtype=np.float32)


def prepare_encoder_input(image_rgb: np.ndarray) -> np.ndarray:
    """将人物头像裁图转换成模型输入。"""
    if image_rgb.ndim == 2:
        image_rgb = cv2.cvtColor(image_rgb, cv2.COLOR_GRAY2RGB)
    elif image_rgb.shape[2] == 4:
        image_rgb = cv2.cvtColor(image_rgb, cv2.COLOR_RGBA2RGB)
    resized = cv2.resize(
        image_rgb,
        (INPUT_IMAGE_SIZE, INPUT_IMAGE_SIZE),
        interpolation=cv2.INTER_AREA,
    )
    normalized = resized.astype(np.float32) / 255.0
    return np.transpose(normalized, (2, 0, 1))


def cosine_similarity(query: np.ndarray, bank: np.ndarray) -> np.ndarray:
    """返回 query 与 bank 每个向量之间的余弦相似度。"""
    if bank.size == 0:
        return np.empty((0,), dtype=np.float32)
    return bank @ query.astype(np.float32, copy=False)


def load_reference_bank(path: str | Path) -> PortraitReferenceBank:
    """加载人物头像向量库。"""
    payload = np.load(Path(path), allow_pickle=False)
    return PortraitReferenceBank(
        servant_name=str(payload["servant_name"][0]),
        square_positive=np.asarray(payload["square_positive"], dtype=np.float32),
        face_positive=np.asarray(payload["face_positive"], dtype=np.float32),
        square_negative=np.asarray(payload["square_negative"], dtype=np.float32),
        face_negative=np.asarray(payload["face_negative"], dtype=np.float32),
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
        source_names=np.asarray(bank.source_names),
        negative_names=np.asarray(bank.negative_names),
    )


def ensure_portrait_encoder_model(path: str | Path) -> Path:
    """确保运行时 ONNX 模型存在。"""
    target = Path(path)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    projection = _build_projection_matrix()
    model = _build_onnx_model(projection)
    onnx.checker.check_model(model)
    onnx.save(model, target)
    return target


def _build_projection_matrix() -> np.ndarray:
    rng = np.random.default_rng(PROJECTION_SEED)
    matrix = rng.standard_normal((INPUT_VECTOR_LENGTH, EMBEDDING_DIM)).astype(np.float32)
    matrix /= np.sqrt(float(INPUT_VECTOR_LENGTH))
    return matrix


def _build_onnx_model(projection: np.ndarray) -> onnx.ModelProto:
    input_info = oh.make_tensor_value_info(
        "input",
        onnx.TensorProto.FLOAT,
        ["batch", 3, INPUT_IMAGE_SIZE, INPUT_IMAGE_SIZE],
    )
    output_info = oh.make_tensor_value_info(
        "embedding",
        onnx.TensorProto.FLOAT,
        ["batch", EMBEDDING_DIM],
    )
    projection_tensor = oh.make_tensor(
        "projection",
        onnx.TensorProto.FLOAT,
        projection.shape,
        projection.flatten().tolist(),
    )
    epsilon_tensor = oh.make_tensor("epsilon", onnx.TensorProto.FLOAT, [1], [1e-6])
    nodes = [
        oh.make_node("Flatten", inputs=["input"], outputs=["flat"], axis=1),
        oh.make_node(
            "ReduceMean",
            inputs=["flat"],
            outputs=["flat_mean"],
            axes=[1],
            keepdims=1,
        ),
        oh.make_node("Sub", inputs=["flat", "flat_mean"], outputs=["centered"]),
        oh.make_node(
            "MatMul",
            inputs=["centered", "projection"],
            outputs=["projected"],
        ),
        oh.make_node(
            "ReduceL2",
            inputs=["projected"],
            outputs=["norm"],
            axes=[1],
            keepdims=1,
        ),
        oh.make_node("Max", inputs=["norm", "epsilon"], outputs=["safe_norm"]),
        oh.make_node("Div", inputs=["projected", "safe_norm"], outputs=["embedding"]),
    ]
    graph = oh.make_graph(
        nodes,
        "portrait_encoder",
        [input_info],
        [output_info],
        initializer=[projection_tensor, epsilon_tensor],
    )
    model = oh.make_model(
        graph,
        producer_name="lumina",
        opset_imports=[oh.make_opsetid("", 11)],
    )
    model.ir_version = onnx.IR_VERSION
    return model


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
    alpha = (image_rgba[:, :, 3:4].astype(np.float32) / 255.0)
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


def bank_counts(bank: PortraitReferenceBank) -> dict[str, int]:
    """返回向量库样本数量，便于调试输出。"""
    return {
        "square_positive": int(bank.square_positive.shape[0]),
        "face_positive": int(bank.face_positive.shape[0]),
        "square_negative": int(bank.square_negative.shape[0]),
        "face_negative": int(bank.face_negative.shape[0]),
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
    }
