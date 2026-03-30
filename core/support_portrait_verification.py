"""助战页人物头像向量核验。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from core.config import SupportRecognitionConfig
from core.coordinates import GameCoordinates
from core.portrait_embedding import (
    PortraitEncoder,
    PortraitReferenceBank,
    PortraitReferenceMeta,
    cosine_similarity,
    load_reference_bank,
    write_png,
)
from core.resources import ResourceCatalog

log = logging.getLogger("core.support_portrait_verification")

OFFSET_MIN = -220
OFFSET_MAX = 40
OFFSET_STEP = 4
REGION_CONFIRM_TOLERANCE = 24


@dataclass(frozen=True)
class SupportPortraitSlotScore:
    """描述单个助战位的核验结果。"""

    slot_index: int
    score: float
    region: tuple[int, int, int, int]
    click_position: tuple[int, int]
    positive_score: float
    negative_score: float
    square_positive: float
    face_positive: float
    square_negative: float
    face_negative: float
    best_positive_name: str = ""
    best_negative_name: str = ""


@dataclass(frozen=True)
class SupportPortraitVerification:
    """描述当前截图里的三个位核验结果。"""

    servant_name: str
    slot_scores: list[SupportPortraitSlotScore]
    best_slot: Optional[SupportPortraitSlotScore]
    second_slot: Optional[SupportPortraitSlotScore]
    margin: float
    min_score: float
    min_margin: float


@dataclass(frozen=True)
class SupportPortraitVerifyResult:
    """描述一次确认后的最终命中。"""

    slot_index: int
    click_position: tuple[int, int]
    score: float
    confirm_score: float
    margin: float
    best_positive_name: str
    best_negative_name: str


class SupportPortraitVerifier:
    """对固定小区域的人物头像做目标核验。"""

    def __init__(
        self,
        servant_name: str,
        bank: PortraitReferenceBank,
        meta: PortraitReferenceMeta,
        config: SupportRecognitionConfig,
        resources: ResourceCatalog,
        encoder: Optional[PortraitEncoder] = None,
    ) -> None:
        self.servant_name = servant_name
        self.bank = bank
        self.meta = meta
        self.config = config
        self.resources = resources
        model_path = Path(resources.assets_dir) / meta.model_path
        self.encoder = encoder or PortraitEncoder(model_path)
        self.min_score = (
            float(config.min_slot_score)
            if float(config.min_slot_score) > 0
            else float(meta.min_score)
        )
        self.min_margin = (
            float(config.min_slot_margin)
            if float(config.min_slot_margin) > 0
            else float(meta.min_margin)
        )

    @classmethod
    def from_servant(
        cls,
        servant_name: str,
        resources: ResourceCatalog,
        config: SupportRecognitionConfig,
        encoder: Optional[PortraitEncoder] = None,
    ) -> "SupportPortraitVerifier":
        manifest = resources.load_servant_manifest(servant_name)
        if manifest is None:
            raise FileNotFoundError(f"未找到从者资料：{servant_name}")
        bank_path = Path(resources.support_reference_bank_path(servant_name, manifest))
        meta_path = Path(resources.support_reference_meta_path(servant_name, manifest))
        if not bank_path.exists():
            raise FileNotFoundError(f"未找到人物头像向量库：{bank_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"未找到人物头像元数据：{meta_path}")
        bank = load_reference_bank(bank_path)
        meta = PortraitReferenceMeta.from_json(meta_path)
        return cls(
            servant_name=servant_name,
            bank=bank,
            meta=meta,
            config=config,
            resources=resources,
            encoder=encoder,
        )

    def analyze(self, screen_rgb: np.ndarray) -> SupportPortraitVerification:
        best_slot_scores: list[SupportPortraitSlotScore] = []
        best_metric = -999.0
        best_peak = -999.0
        for offset in range(OFFSET_MIN, OFFSET_MAX + 1, OFFSET_STEP):
            slot_scores = self._score_offset(screen_rgb, offset)
            metric, peak = self._offset_metric(slot_scores)
            if metric > best_metric or (metric == best_metric and peak > best_peak):
                best_metric = metric
                best_peak = peak
                best_slot_scores = slot_scores

        ranked = sorted(best_slot_scores, key=lambda item: item.score, reverse=True)
        best_slot = ranked[0] if ranked else None
        second_slot = ranked[1] if len(ranked) > 1 else None
        margin = best_slot.score - second_slot.score if best_slot and second_slot else 0.0
        return SupportPortraitVerification(
            servant_name=self.servant_name,
            slot_scores=best_slot_scores,
            best_slot=best_slot,
            second_slot=second_slot,
            margin=margin,
            min_score=self.min_score,
            min_margin=self.min_margin,
        )

    def confirm_match(
        self,
        initial_screen_rgb: np.ndarray,
        confirm_screen_rgb: np.ndarray,
    ) -> Optional[SupportPortraitVerifyResult]:
        initial = self.analyze(initial_screen_rgb)
        if not self.is_confident(initial):
            self.save_debug_mismatch(initial_screen_rgb, initial, reason="low_score")
            return None
        confirmed = self.analyze(confirm_screen_rgb)
        if not self.is_confident(confirmed):
            self.save_debug_mismatch(confirm_screen_rgb, confirmed, reason="confirm_low")
            return None
        if initial.best_slot is None or confirmed.best_slot is None:
            return None
        if initial.best_slot.slot_index != confirmed.best_slot.slot_index:
            self.save_debug_mismatch(confirm_screen_rgb, confirmed, reason="slot_changed")
            return None
        if not _regions_close(
            initial.best_slot.region,
            confirmed.best_slot.region,
            tolerance=REGION_CONFIRM_TOLERANCE,
        ):
            self.save_debug_mismatch(confirm_screen_rgb, confirmed, reason="slot_shifted")
            return None
        return SupportPortraitVerifyResult(
            slot_index=initial.best_slot.slot_index,
            click_position=initial.best_slot.click_position,
            score=initial.best_slot.score,
            confirm_score=confirmed.best_slot.score,
            margin=min(initial.margin, confirmed.margin),
            best_positive_name=initial.best_slot.best_positive_name,
            best_negative_name=initial.best_slot.best_negative_name,
        )

    def match_image(self, image_path: Path) -> Optional[SupportPortraitVerifyResult]:
        screen_rgb = _read_image_rgb(image_path)
        return self.confirm_match(screen_rgb, screen_rgb)

    def is_confident(self, analysis: SupportPortraitVerification) -> bool:
        if analysis.best_slot is None:
            return False
        return (
            analysis.best_slot.score >= self.min_score
            and analysis.margin >= self.min_margin
        )

    def save_debug_mismatch(
        self,
        screen_rgb: np.ndarray,
        analysis: SupportPortraitVerification,
        *,
        reason: str,
    ) -> None:
        if not self.config.save_debug_mismatches:
            return
        debug_dir = Path(self.resources.support_debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        annotated = _annotate_support_screen(screen_rgb, analysis)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_path = debug_dir / f"{self.servant_name}_{reason}_{timestamp}.png"
        write_png(save_path, annotated)
        self._prune_debug_dir(debug_dir)

    def _score_offset(
        self,
        screen_rgb: np.ndarray,
        offset: int,
    ) -> list[SupportPortraitSlotScore]:
        strip_region = GameCoordinates.SUPPORT_PORTRAIT_STRIP
        images: list[np.ndarray] = []
        pending: list[tuple[int, tuple[int, int, int, int], tuple[int, int]]] = []
        slot_scores: list[SupportPortraitSlotScore] = []
        for slot_index, base_region in GameCoordinates.SUPPORT_PORTRAIT_SLOT_REGIONS.items():
            region = _shift_region(base_region, dy=offset)
            click_position = GameCoordinates.region_center(region)
            if not _region_inside_strip(region, strip_region):
                slot_scores.append(
                    SupportPortraitSlotScore(
                        slot_index=slot_index,
                        score=0.0,
                        region=region,
                        click_position=click_position,
                        positive_score=0.0,
                        negative_score=0.0,
                        square_positive=0.0,
                        face_positive=0.0,
                        square_negative=0.0,
                        face_negative=0.0,
                    )
                )
                continue
            portrait_crop = _crop_relative(screen_rgb, region, self.meta.portrait_crop)
            face_crop = _crop_relative(screen_rgb, region, self.meta.face_crop)
            if portrait_crop.size == 0 or face_crop.size == 0:
                slot_scores.append(
                    SupportPortraitSlotScore(
                        slot_index=slot_index,
                        score=0.0,
                        region=region,
                        click_position=click_position,
                        positive_score=0.0,
                        negative_score=0.0,
                        square_positive=0.0,
                        face_positive=0.0,
                        square_negative=0.0,
                        face_negative=0.0,
                    )
                )
                continue
            pending.append((slot_index, region, click_position))
            images.extend((portrait_crop, face_crop))

        embeddings = self.encoder.encode_batch(images) if images else np.empty((0, 128), dtype=np.float32)
        pending_index = 0
        complete_scores = {item.slot_index: item for item in slot_scores}
        for slot_index, region, click_position in pending:
            square_vector = embeddings[pending_index]
            face_vector = embeddings[pending_index + 1]
            pending_index += 2
            complete_scores[slot_index] = self._score_slot(
                slot_index=slot_index,
                region=region,
                click_position=click_position,
                square_vector=square_vector,
                face_vector=face_vector,
            )
        return [complete_scores[index] for index in sorted(complete_scores)]

    def _score_slot(
        self,
        *,
        slot_index: int,
        region: tuple[int, int, int, int],
        click_position: tuple[int, int],
        square_vector: np.ndarray,
        face_vector: np.ndarray,
    ) -> SupportPortraitSlotScore:
        square_positive_scores = cosine_similarity(square_vector, self.bank.square_positive)
        face_positive_scores = cosine_similarity(face_vector, self.bank.face_positive)
        square_negative_scores = cosine_similarity(square_vector, self.bank.square_negative)
        face_negative_scores = cosine_similarity(face_vector, self.bank.face_negative)

        square_positive = float(square_positive_scores.max(initial=0.0))
        face_positive = float(face_positive_scores.max(initial=0.0))
        square_negative = float(square_negative_scores.max(initial=0.0))
        face_negative = float(face_negative_scores.max(initial=0.0))
        positive_score = (
            self.meta.square_weight * square_positive
            + self.meta.face_weight * face_positive
        )
        negative_score = (
            self.meta.square_weight * square_negative
            + self.meta.face_weight * face_negative
        )
        final_score = positive_score - (self.meta.negative_penalty * negative_score)
        best_positive_name = _best_name(
            self.bank.source_names,
            square_positive_scores,
            face_positive_scores,
        )
        best_negative_name = _best_name(
            self.bank.negative_names,
            square_negative_scores,
            face_negative_scores,
        )
        return SupportPortraitSlotScore(
            slot_index=slot_index,
            score=float(final_score),
            region=region,
            click_position=click_position,
            positive_score=float(positive_score),
            negative_score=float(negative_score),
            square_positive=square_positive,
            face_positive=face_positive,
            square_negative=square_negative,
            face_negative=face_negative,
            best_positive_name=best_positive_name,
            best_negative_name=best_negative_name,
        )

    def _offset_metric(
        self,
        slot_scores: list[SupportPortraitSlotScore],
    ) -> tuple[float, float]:
        ranked = sorted(slot_scores, key=lambda item: item.score, reverse=True)
        best_slot = ranked[0] if ranked else None
        second_slot = ranked[1] if len(ranked) > 1 else None
        peak_score = best_slot.score if best_slot else 0.0
        margin = peak_score - second_slot.score if best_slot and second_slot else peak_score
        return peak_score + margin, peak_score

    def _prune_debug_dir(self, debug_dir: Path) -> None:
        files = sorted(
            debug_dir.glob(f"{self.servant_name}_*.png"),
            key=lambda item: item.stat().st_mtime,
        )
        excess = len(files) - self.config.max_debug_images
        if excess <= 0:
            return
        for old_file in files[:excess]:
            old_file.unlink(missing_ok=True)


def _best_name(
    names: list[str],
    square_scores: np.ndarray,
    face_scores: np.ndarray,
) -> str:
    if not names:
        return ""
    square_max = square_scores.max(initial=0.0) if square_scores.size else 0.0
    face_max = face_scores.max(initial=0.0) if face_scores.size else 0.0
    if face_max >= square_max and face_scores.size:
        return names[int(face_scores.argmax())]
    if square_scores.size:
        return names[int(square_scores.argmax())]
    return ""


def _crop_relative(
    image_rgb: np.ndarray,
    region: tuple[int, int, int, int],
    relative_region: tuple[int, int, int, int],
) -> np.ndarray:
    x1, y1, _, _ = region
    rx1, ry1, rx2, ry2 = relative_region
    return _safe_crop(image_rgb, x1 + rx1, y1 + ry1, x1 + rx2, y1 + ry2)


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
        return np.empty((0, 0, 3), dtype=np.uint8)
    return image_rgb[top:bottom, left:right]


def _annotate_support_screen(
    screen_rgb: np.ndarray,
    analysis: SupportPortraitVerification,
) -> np.ndarray:
    annotated = cv2.cvtColor(screen_rgb, cv2.COLOR_RGB2BGR)
    strip_x1, strip_y1, strip_x2, strip_y2 = GameCoordinates.SUPPORT_PORTRAIT_STRIP
    cv2.rectangle(annotated, (strip_x1, strip_y1), (strip_x2, strip_y2), (255, 128, 0), 1)
    for item in analysis.slot_scores:
        color = (
            (0, 255, 0)
            if analysis.best_slot and item.slot_index == analysis.best_slot.slot_index
            else (0, 128, 255)
        )
        x1, y1, x2, y2 = item.region
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            f"S{item.slot_index}:{item.score:.3f}",
            (x1 + 4, max(24, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )
    return cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)


def _read_image_rgb(image_path: Path) -> np.ndarray:
    raw = np.fromfile(str(image_path), dtype=np.uint8)
    if raw.size == 0:
        raise FileNotFoundError(f"无法读取截图：{image_path}")
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"无法读取截图：{image_path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _regions_close(
    region_a: tuple[int, int, int, int],
    region_b: tuple[int, int, int, int],
    *,
    tolerance: int,
) -> bool:
    center_a = ((region_a[0] + region_a[2]) // 2, (region_a[1] + region_a[3]) // 2)
    center_b = ((region_b[0] + region_b[2]) // 2, (region_b[1] + region_b[3]) // 2)
    return abs(center_a[0] - center_b[0]) <= tolerance and abs(center_a[1] - center_b[1]) <= tolerance


def _shift_region(
    region: tuple[int, int, int, int],
    *,
    dy: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = region
    return (x1, y1 + dy, x2, y2 + dy)


def _region_inside_strip(
    region: tuple[int, int, int, int],
    strip_region: tuple[int, int, int, int],
) -> bool:
    x1, y1, x2, y2 = region
    strip_x1, strip_y1, strip_x2, strip_y2 = strip_region
    return x1 >= strip_x1 and x2 <= strip_x2 and y1 >= strip_y1 and y2 <= strip_y2
