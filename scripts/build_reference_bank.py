"""生成人物头像向量库与默认阈值。"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import SupportRecognitionConfig
from core.coordinates import GameCoordinates
from core.portrait_embedding import (
    DEFAULT_MIN_MARGIN,
    DEFAULT_MIN_SCORE,
    PortraitEncoder,
    PortraitReferenceBank,
    PortraitReferenceMeta,
    ensure_portrait_encoder_model,
    load_rgba_image,
    load_rgb_image,
    rgba_to_rgb_on_black,
    save_reference_bank,
    write_png,
)
from core.resources import ResourceCatalog
from core.support_portrait_verification import SupportPortraitVerifier

DEFAULT_POSITIVE_IMAGES = [
    "test_image/助战选择界面摩根1.png",
    "test_image/助战选择界面摩根2.png",
    "test_image/助战选择界面摩根3.png",
    "test_image/助战选择界面摩根5.png",
    "test_image/失败测试图片.png",
]
DEFAULT_NEGATIVE_IMAGES = [
    "test_image/失败测试图片2.png",
    "test_image/失败测试图片3.png",
]
SOURCE_FACE_CROP = (0, 0, 128, 96)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成人物头像向量库")
    parser.add_argument("--servant", required=True, help="从者目录名")
    parser.add_argument(
        "--positive-images",
        nargs="+",
        default=[],
        help="正例截图路径，留空时 Morgan 使用仓库内默认样本",
    )
    parser.add_argument(
        "--negative-images",
        nargs="+",
        default=[],
        help="反例截图路径，留空时 Morgan 使用仓库内默认样本",
    )
    parser.add_argument(
        "--expected-slot",
        type=int,
        default=2,
        help="正例里目标从者所在助战位",
    )
    parser.add_argument(
        "--keep-preview",
        action="store_true",
        help="保留简单预览图",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resources = ResourceCatalog(str(REPO_ROOT / "assets"))
    manifest = resources.load_servant_manifest(args.servant)
    if manifest is None:
        raise FileNotFoundError(f"未找到从者资料：{args.servant}")

    positive_images = _resolve_sample_paths(
        args.positive_images,
        DEFAULT_POSITIVE_IMAGES,
        args.servant,
    )
    negative_images = _resolve_sample_paths(
        args.negative_images,
        DEFAULT_NEGATIVE_IMAGES,
        args.servant,
    )
    generated_dir = Path(resources.support_generated_dir(args.servant, manifest))

    model_path = ensure_portrait_encoder_model(resources.portrait_encoder_model())
    encoder = PortraitEncoder(model_path)
    meta = PortraitReferenceMeta(
        servant_name=args.servant,
        model_path=str(Path("models") / model_path.name),
        image_size=24,
        embedding_dim=128,
        positive_samples=[path.name for path in positive_images],
        negative_samples=[path.name for path in negative_images],
    )
    bank = _build_reference_bank(
        servant_name=args.servant,
        resources=resources,
        manifest=manifest,
        encoder=encoder,
        meta=meta,
        positive_images=positive_images,
        negative_images=negative_images,
        expected_slot=args.expected_slot,
    )
    verifier = SupportPortraitVerifier(
        servant_name=args.servant,
        bank=bank,
        meta=meta,
        config=SupportRecognitionConfig(
            backend="embedding",
            min_slot_score=0.0,
            min_slot_margin=0.0,
            save_debug_mismatches=False,
        ),
        resources=resources,
        encoder=encoder,
    )
    calibrated_meta = _calibrate_meta(
        base_meta=meta,
        verifier=verifier,
        positive_images=positive_images,
        negative_images=negative_images,
        expected_slot=args.expected_slot,
    )

    _clear_generated_dir(generated_dir)
    save_reference_bank(generated_dir / "reference_bank.npz", bank)
    calibrated_meta.to_json(generated_dir / "reference_meta.json")
    if args.keep_preview:
        _write_preview(generated_dir / "positive_preview.png", bank.square_positive)
        _write_preview(generated_dir / "negative_preview.png", bank.square_negative)

    print(
        f"{args.servant}: positive={len(positive_images)} negative={len(negative_images)} "
        f"min_score={calibrated_meta.min_score:.3f} min_margin={calibrated_meta.min_margin:.3f}"
    )
    return 0


def _build_reference_bank(
    *,
    servant_name: str,
    resources: ResourceCatalog,
    manifest,
    encoder: PortraitEncoder,
    meta: PortraitReferenceMeta,
    positive_images: list[Path],
    negative_images: list[Path],
    expected_slot: int,
) -> PortraitReferenceBank:
    source_dir = Path(resources.support_source_dir(servant_name, manifest))
    source_paths = sorted(source_dir.glob(manifest.support_recognition.source_glob))
    if not source_paths:
        raise FileNotFoundError(f"未找到 atlas 原图：{source_dir}")

    square_positive_images: list[np.ndarray] = []
    face_positive_images: list[np.ndarray] = []
    source_names: list[str] = []
    for source_path in source_paths:
        image_rgba = load_rgba_image(source_path)
        image_rgb = rgba_to_rgb_on_black(image_rgba)
        square_positive_images.append(image_rgb)
        face_positive_images.append(_safe_crop(image_rgb, *SOURCE_FACE_CROP))
        source_names.append(f"source:{source_path.name}")

    for image_path in positive_images:
        screen_rgb = load_rgb_image(image_path)
        expected_region = GameCoordinates.SUPPORT_PORTRAIT_SLOT_REGIONS[expected_slot]
        square_crop, face_crop = _slot_views(screen_rgb, expected_region, meta)
        square_positive_images.append(square_crop)
        face_positive_images.append(face_crop)
        source_names.append(f"positive:{image_path.name}")

    square_negative_images: list[np.ndarray] = []
    face_negative_images: list[np.ndarray] = []
    negative_names: list[str] = []
    for image_path in positive_images:
        screen_rgb = load_rgb_image(image_path)
        for slot_index, region in GameCoordinates.SUPPORT_PORTRAIT_SLOT_REGIONS.items():
            if slot_index == expected_slot:
                continue
            square_crop, face_crop = _slot_views(screen_rgb, region, meta)
            square_negative_images.append(square_crop)
            face_negative_images.append(face_crop)
            negative_names.append(f"positive_other:{image_path.name}:slot{slot_index}")
    for image_path in negative_images:
        screen_rgb = load_rgb_image(image_path)
        for slot_index, region in GameCoordinates.SUPPORT_PORTRAIT_SLOT_REGIONS.items():
            square_crop, face_crop = _slot_views(screen_rgb, region, meta)
            square_negative_images.append(square_crop)
            face_negative_images.append(face_crop)
            negative_names.append(f"negative:{image_path.name}:slot{slot_index}")

    return PortraitReferenceBank(
        servant_name=servant_name,
        square_positive=encoder.encode_batch(square_positive_images),
        face_positive=encoder.encode_batch(face_positive_images),
        square_negative=encoder.encode_batch(square_negative_images),
        face_negative=encoder.encode_batch(face_negative_images),
        source_names=source_names,
        negative_names=negative_names,
    )


def _calibrate_meta(
    *,
    base_meta: PortraitReferenceMeta,
    verifier: SupportPortraitVerifier,
    positive_images: list[Path],
    negative_images: list[Path],
    expected_slot: int,
) -> PortraitReferenceMeta:
    positive_scores: list[float] = []
    positive_margins: list[float] = []
    negative_scores: list[float] = []
    negative_margins: list[float] = []

    for image_path in positive_images:
        analysis = verifier.analyze(load_rgb_image(image_path))
        target = next(
            (item for item in analysis.slot_scores if item.slot_index == expected_slot),
            None,
        )
        if target is not None:
            positive_scores.append(float(target.score))
        if analysis.best_slot is not None and analysis.best_slot.slot_index == expected_slot:
            positive_margins.append(float(analysis.margin))

    for image_path in negative_images:
        analysis = verifier.analyze(load_rgb_image(image_path))
        if analysis.best_slot is not None:
            negative_scores.append(float(analysis.best_slot.score))
            negative_margins.append(float(analysis.margin))

    min_positive_score = min(positive_scores) if positive_scores else DEFAULT_MIN_SCORE
    max_negative_score = max(negative_scores) if negative_scores else 0.0
    min_positive_margin = min(positive_margins) if positive_margins else DEFAULT_MIN_MARGIN
    max_negative_margin = max(negative_margins) if negative_margins else 0.0

    min_score = max(DEFAULT_MIN_SCORE, max_negative_score + 0.02)
    if min_positive_score > min_score:
        min_score = min(min_score, min_positive_score - 0.01)
    else:
        min_score = max(DEFAULT_MIN_SCORE, min_positive_score * 0.95)

    min_margin = max(DEFAULT_MIN_MARGIN, max_negative_margin + 0.02)
    if min_positive_margin > min_margin:
        min_margin = min(min_margin, min_positive_margin - 0.01)
    else:
        min_margin = max(DEFAULT_MIN_MARGIN, min_positive_margin * 0.95)

    return PortraitReferenceMeta(
        servant_name=base_meta.servant_name,
        model_path=base_meta.model_path,
        image_size=base_meta.image_size,
        embedding_dim=base_meta.embedding_dim,
        square_weight=base_meta.square_weight,
        face_weight=base_meta.face_weight,
        negative_penalty=base_meta.negative_penalty,
        min_score=float(min_score),
        min_margin=float(min_margin),
        portrait_crop=base_meta.portrait_crop,
        face_crop=base_meta.face_crop,
        positive_samples=base_meta.positive_samples,
        negative_samples=base_meta.negative_samples,
    )


def _resolve_sample_paths(
    provided: list[str],
    defaults: list[str],
    servant_name: str,
) -> list[Path]:
    raw_paths = provided or (defaults if servant_name == "morgan" else [])
    if not raw_paths:
        return []
    paths = [REPO_ROOT / item for item in raw_paths]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"样本截图不存在：{missing}")
    return paths


def _slot_views(
    screen_rgb: np.ndarray,
    region: tuple[int, int, int, int],
    meta: PortraitReferenceMeta,
) -> tuple[np.ndarray, np.ndarray]:
    x1, y1, _, _ = region
    square_crop = _safe_crop(
        screen_rgb,
        x1 + meta.portrait_crop[0],
        y1 + meta.portrait_crop[1],
        x1 + meta.portrait_crop[2],
        y1 + meta.portrait_crop[3],
    )
    face_crop = _safe_crop(
        screen_rgb,
        x1 + meta.face_crop[0],
        y1 + meta.face_crop[1],
        x1 + meta.face_crop[2],
        y1 + meta.face_crop[3],
    )
    return square_crop, face_crop


def _safe_crop(
    image_rgb: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> np.ndarray:
    height, width = image_rgb.shape[:2]
    left = max(0, min(x1, width))
    right = max(0, min(x2, width))
    top = max(0, min(y1, height))
    bottom = max(0, min(y2, height))
    if right <= left or bottom <= top:
        return np.zeros((24, 24, 3), dtype=np.uint8)
    return image_rgb[top:bottom, left:right]


def _clear_generated_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_preview(path: Path, vectors: np.ndarray) -> None:
    if vectors.size == 0:
        return
    rows = min(vectors.shape[0], 12)
    preview = np.zeros((rows * 24, 24, 3), dtype=np.uint8)
    for index in range(rows):
        row = index * 24
        value = int(min(255, max(0, (float(vectors[index, 0]) + 1.0) * 127.5)))
        preview[row : row + 24, :, :] = value
    write_png(path, preview)


if __name__ == "__main__":
    raise SystemExit(main())
