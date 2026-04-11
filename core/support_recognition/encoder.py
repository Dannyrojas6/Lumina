"""助战头像向量编码。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import onnx
import onnx.helper as oh
import onnxruntime as ort

INPUT_IMAGE_SIZE = 24
INPUT_VECTOR_LENGTH = INPUT_IMAGE_SIZE * INPUT_IMAGE_SIZE * 3
EMBEDDING_DIM = 128
PROJECTION_SEED = 7040


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
        oh.make_node("MatMul", inputs=["centered", "projection"], outputs=["projected"]),
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
