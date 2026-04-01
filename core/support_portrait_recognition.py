"""助战头像模板生成与局部匹配。"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from core.config import SupportRecognitionConfig
from core.coordinates import GameCoordinates
from core.image_recognizer import ImageRecognizer
from core.resources import ResourceCatalog, ServantManifest

log = logging.getLogger("core.support_portrait_recognition")

TEMPLATE_VARIANTS = ("full_gray", "full_edge", "face_gray", "face_edge")
COARSE_VARIANTS = ("full_gray", "face_gray")
VARIANT_WEIGHTS = {
    "full_gray": 0.35,
    "face_gray": 0.45,
    "full_edge": 0.10,
    "face_edge": 0.10,
}
OFFSET_MIN = -220
OFFSET_MAX = 40
COARSE_OFFSET_STEP = 16
FINE_OFFSET_STEP = 4
COARSE_TOP_N = 2
COARSE_REFINE_RADIUS = 8


@dataclass(frozen=True)
class SupportTemplateVariant:
    """描述单张可匹配模板。"""

    source_name: str
    variant_name: str
    image_path: Path
    mask_path: Optional[Path] = None


@dataclass(frozen=True)
class SupportSlotScore:
    """描述某个助战位的综合评分结果。"""

    slot_index: int
    score: float
    region: tuple[int, int, int, int]
    click_position: tuple[int, int]
    template_path: Optional[str] = None
    variant_name: str = ""
    component_scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SupportPortraitAnalysis:
    """描述当前截图里的助战头像分析结果。"""

    servant_name: str
    slot_scores: list[SupportSlotScore]
    best_slot: Optional[SupportSlotScore]
    second_slot: Optional[SupportSlotScore]
    margin: float


@dataclass(frozen=True)
class SupportPortraitMatchResult:
    """描述一次通过确认后的助战命中。"""

    slot_index: int
    click_position: tuple[int, int]
    score: float
    confirm_score: float
    margin: float
    template_path: str
    variant_name: str


class SupportPortraitGenerator:
    """将 atlas 原图转换成可直接匹配的模板。"""

    def __init__(self, resources: ResourceCatalog) -> None:
        self.resources = resources

    def build_for_servant(self, servant_name: str, *, clean: bool = True) -> list[Path]:
        manifest = self._require_manifest(servant_name)
        source_dir = Path(self.resources.support_source_dir(servant_name, manifest))
        generated_dir = _template_generated_dir(
            Path(self.resources.support_generated_dir(servant_name, manifest))
        )
        source_paths = sorted(source_dir.glob(manifest.support_recognition.source_glob))
        if not source_paths:
            raise FileNotFoundError(f"未找到助战头像原图：{source_dir}")

        generated_dir.mkdir(parents=True, exist_ok=True)
        if clean:
            self._clear_generated_dir(generated_dir)

        built_paths: list[Path] = []
        index_data: list[dict[str, object]] = []
        for source_path in source_paths:
            variant_dir = generated_dir / source_path.stem
            variant_dir.mkdir(parents=True, exist_ok=True)
            rgba = self._load_rgba(source_path)
            full_rgba = self._prepare_full_rgba(rgba)
            face_rgba, face_box = self._prepare_face_rgba(full_rgba)
            built_paths.extend(
                self._write_variant_group(
                    variant_dir=variant_dir,
                    source_name=source_path.name,
                    full_rgba=full_rgba,
                    face_rgba=face_rgba,
                )
            )
            metadata = {
                "source": source_path.name,
                "face_box": list(face_box),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            metadata_path = variant_dir / "metadata.json"
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            built_paths.append(metadata_path)
            index_data.append(metadata)

        index_path = generated_dir / "index.json"
        index_path.write_text(
            json.dumps(index_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        built_paths.append(index_path)
        return built_paths

    def _require_manifest(self, servant_name: str) -> ServantManifest:
        manifest = self.resources.load_servant_manifest(servant_name)
        if manifest is None:
            raise FileNotFoundError(f"未找到从者资料：{servant_name}")
        return manifest

    def _clear_generated_dir(self, generated_dir: Path) -> None:
        for path in sorted(generated_dir.glob("**/*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()

    def _write_variant_group(
        self,
        *,
        variant_dir: Path,
        source_name: str,
        full_rgba: np.ndarray,
        face_rgba: np.ndarray,
    ) -> list[Path]:
        outputs: list[Path] = []
        full_gray, full_gray_mask = self._build_gray_variant(full_rgba)
        full_edge, full_edge_mask = self._build_edge_variant(full_rgba)
        face_gray, face_gray_mask = self._build_gray_variant(face_rgba)
        face_edge, face_edge_mask = self._build_edge_variant(face_rgba)
        variants = {
            "full_gray": (full_gray, full_gray_mask),
            "full_edge": (full_edge, full_edge_mask),
            "face_gray": (face_gray, face_gray_mask),
            "face_edge": (face_edge, face_edge_mask),
        }
        for variant_name, (image, mask) in variants.items():
            image_path = variant_dir / f"{variant_name}.png"
            mask_path = variant_dir / f"{variant_name}_mask.png"
            _write_png(image_path, image)
            _write_png(mask_path, mask)
            outputs.extend((image_path, mask_path))
            log.debug(
                "已生成助战模板 servant=%s source=%s variant=%s",
                variant_dir.parent.parent.name,
                source_name,
                variant_name,
            )
        return outputs

    def _load_rgba(self, source_path: Path) -> np.ndarray:
        image = _read_image(source_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise FileNotFoundError(f"无法读取助战头像原图：{source_path}")
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
        elif image.shape[2] == 3:
            alpha = np.full(image.shape[:2], 255, dtype=np.uint8)
            image = np.dstack([image, alpha])
        return image

    def _prepare_full_rgba(self, rgba: np.ndarray) -> np.ndarray:
        return cv2.resize(rgba, (128, 128), interpolation=cv2.INTER_CUBIC)

    def _prepare_face_rgba(
        self, rgba: np.ndarray
    ) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        height, width = rgba.shape[:2]
        x1, x2 = 0, width
        y_top = 0
        y_bottom = max(24, int(height * 0.68))
        face = rgba[y_top:y_bottom, x1:x2]
        resized = cv2.resize(face, (128, 88), interpolation=cv2.INTER_CUBIC)
        return resized, (x1, y_top, x2, y_bottom)

    def _build_gray_variant(self, rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        bgr = rgba[:, :, :3]
        alpha = rgba[:, :, 3]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        alpha_f = alpha.astype(np.float32) / 255.0
        blended = np.clip(gray.astype(np.float32) * alpha_f, 0, 255).astype(np.uint8)
        mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
        return blended, mask

    def _build_edge_variant(self, rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        gray, alpha_mask = self._build_gray_variant(rgba)
        edge = cv2.Canny(gray, 48, 140)
        mask = np.where(edge > 0, 255, 0).astype(np.uint8)
        if not np.any(mask):
            mask = alpha_mask
        return edge, mask


class SupportPortraitMatcher:
    """在助战头像区域里识别目标从者。"""

    def __init__(
        self,
        servant_name: str,
        templates: list[SupportTemplateVariant],
        config: SupportRecognitionConfig,
        resources: ResourceCatalog,
        recognizer: Optional[ImageRecognizer] = None,
    ) -> None:
        if not templates:
            raise ValueError(f"从者 {servant_name} 没有可用助战模板")
        self.servant_name = servant_name
        self.templates = templates
        self.config = config
        self.resources = resources
        self.recognizer = recognizer or ImageRecognizer(threshold=config.min_slot_score)
        self._templates_by_variant: dict[str, list[SupportTemplateVariant]] = {}
        for template in templates:
            self._templates_by_variant.setdefault(template.variant_name, []).append(
                template
            )
        self._image_cache: dict[Path, np.ndarray] = {}
        self._mask_cache: dict[Path, np.ndarray] = {}

    @classmethod
    def from_servant(
        cls,
        servant_name: str,
        resources: ResourceCatalog,
        config: SupportRecognitionConfig,
        recognizer: Optional[ImageRecognizer] = None,
    ) -> "SupportPortraitMatcher":
        manifest = resources.load_servant_manifest(servant_name)
        if manifest is None:
            raise FileNotFoundError(f"未找到从者资料：{servant_name}")
        generated_dir = _template_generated_dir(
            Path(resources.support_generated_dir(servant_name, manifest))
        )
        templates = _load_generated_variants(generated_dir)
        if not templates:
            legacy_path = Path(resources.servant_template(servant_name))
            if legacy_path.exists():
                templates = [
                    SupportTemplateVariant(
                        source_name=legacy_path.name,
                        variant_name="legacy_gray",
                        image_path=legacy_path,
                    )
                ]
        return cls(
            servant_name=servant_name,
            templates=templates,
            config=config,
            resources=resources,
            recognizer=recognizer,
        )

    def analyze(self, screen_rgb: np.ndarray) -> SupportPortraitAnalysis:
        gray = _prepare_screen_gray(screen_rgb)
        edge = cv2.Canny(gray, 48, 140)
        best_slot_scores: list[SupportSlotScore] = []
        best_metric = -1.0
        best_peak_score = -1.0
        candidate_offsets = self._select_candidate_offsets(gray, edge)
        for offset in candidate_offsets:
            slot_scores = self._score_offset(gray, edge, offset)
            metric, peak_score = self._offset_metric(slot_scores)
            if metric > best_metric or (
                metric == best_metric and peak_score > best_peak_score
            ):
                best_metric = metric
                best_peak_score = peak_score
                best_slot_scores = slot_scores

        slot_scores = best_slot_scores
        ranked = sorted(slot_scores, key=lambda item: item.score, reverse=True)
        best_slot = ranked[0] if ranked else None
        second_slot = ranked[1] if len(ranked) > 1 else None
        margin = best_slot.score - second_slot.score if best_slot and second_slot else 0.0
        return SupportPortraitAnalysis(
            servant_name=self.servant_name,
            slot_scores=slot_scores,
            best_slot=best_slot,
            second_slot=second_slot,
            margin=margin,
        )

    def confirm_match(
        self,
        initial_screen_rgb: np.ndarray,
        confirm_screen_rgb: np.ndarray,
    ) -> Optional[SupportPortraitMatchResult]:
        initial = self.analyze(initial_screen_rgb)
        if not self.is_confident(initial):
            self.save_debug_mismatch(initial_screen_rgb, initial, reason="low_score")
            return None

        confirmed = self.analyze(confirm_screen_rgb)
        if not self.is_confident(confirmed):
            self.save_debug_mismatch(confirm_screen_rgb, confirmed, reason="confirm_low")
            return None

        if confirmed.best_slot is None or initial.best_slot is None:
            return None
        if not _regions_close(initial.best_slot.region, confirmed.best_slot.region, tolerance=24):
            self.save_debug_mismatch(confirm_screen_rgb, confirmed, reason="slot_changed")
            return None

        return SupportPortraitMatchResult(
            slot_index=initial.best_slot.slot_index,
            click_position=initial.best_slot.click_position,
            score=initial.best_slot.score,
            confirm_score=confirmed.best_slot.score,
            margin=min(initial.margin, confirmed.margin),
            template_path=initial.best_slot.template_path or "",
            variant_name=initial.best_slot.variant_name,
        )

    def match_image(self, image_path: Path) -> Optional[SupportPortraitMatchResult]:
        screen_rgb = _read_image_rgb(image_path)
        return self.confirm_match(screen_rgb, screen_rgb)

    def is_confident(self, analysis: SupportPortraitAnalysis) -> bool:
        if analysis.best_slot is None:
            return False
        return (
            analysis.best_slot.score >= self.config.min_slot_score
            and analysis.margin >= self.config.min_slot_margin
        )

    def save_debug_mismatch(
        self,
        screen_rgb: np.ndarray,
        analysis: SupportPortraitAnalysis,
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
        _write_png(save_path, annotated)
        self._prune_debug_dir(debug_dir)

    def _score_region(
        self,
        crop_gray: np.ndarray,
        crop_edge: np.ndarray,
        *,
        variant_names: tuple[str, ...] = TEMPLATE_VARIANTS,
    ) -> tuple[float, dict[str, float], str, str]:
        component_scores = {variant_name: 0.0 for variant_name in TEMPLATE_VARIANTS}
        best_template_path = ""
        best_variant_name = ""
        best_variant_score = 0.0
        for variant_name in variant_names:
            for template in self._templates_by_variant.get(variant_name, []):
                search_image = crop_edge if variant_name.endswith("edge") else crop_gray
                template_image = self._load_template(template.image_path)
                template_mask = self._load_mask(template.mask_path)
                match = self.recognizer.match_array_with_score(
                    template=template_image,
                    screen=search_image,
                    threshold=-1.0,
                    mask=template_mask,
                    label=f"{self.servant_name}:{template.source_name}:{template.variant_name}",
                    log_debug=False,
                )
                if match.score > component_scores.get(variant_name, 0.0):
                    component_scores[variant_name] = match.score
                if match.score > best_variant_score:
                    best_variant_score = match.score
                    best_template_path = str(template.image_path)
                    best_variant_name = template.variant_name
        combined = self._combine_component_scores(
            component_scores,
            variant_names=variant_names,
        )
        return combined, component_scores, best_template_path, best_variant_name

    def _select_candidate_offsets(
        self,
        gray: np.ndarray,
        edge: np.ndarray,
    ) -> list[int]:
        ranked_offsets: list[tuple[float, float, int]] = []
        for offset in range(OFFSET_MIN, OFFSET_MAX + 1, COARSE_OFFSET_STEP):
            slot_scores = self._score_offset(gray, edge, offset, variant_names=COARSE_VARIANTS)
            metric, peak_score = self._offset_metric(slot_scores)
            ranked_offsets.append((metric, peak_score, offset))

        ranked_offsets.sort(reverse=True)
        candidate_offsets: set[int] = set()
        for _, _, coarse_offset in ranked_offsets[:COARSE_TOP_N]:
            start = max(OFFSET_MIN, coarse_offset - COARSE_REFINE_RADIUS)
            end = min(OFFSET_MAX, coarse_offset + COARSE_REFINE_RADIUS)
            for offset in range(start, end + 1, FINE_OFFSET_STEP):
                candidate_offsets.add(offset)
        if not candidate_offsets:
            candidate_offsets.add(0)
        return sorted(candidate_offsets)

    def _score_offset(
        self,
        gray: np.ndarray,
        edge: np.ndarray,
        offset: int,
        *,
        variant_names: tuple[str, ...] = TEMPLATE_VARIANTS,
    ) -> list[SupportSlotScore]:
        strip_region = GameCoordinates.SUPPORT_PORTRAIT_STRIP
        slot_scores: list[SupportSlotScore] = []
        for slot_index, base_region in GameCoordinates.SUPPORT_PORTRAIT_SLOT_REGIONS.items():
            region = _shift_region(base_region, dy=offset)
            x1, y1, x2, y2 = region
            if not _region_inside_strip(region, strip_region):
                slot_scores.append(
                    SupportSlotScore(
                        slot_index=slot_index,
                        score=0.0,
                        region=region,
                        click_position=GameCoordinates.region_center(region),
                    )
                )
                continue

            crop_gray = gray[y1:y2, x1:x2]
            crop_edge = edge[y1:y2, x1:x2]
            score, component_scores, template_path, variant_name = self._score_region(
                crop_gray,
                crop_edge,
                variant_names=variant_names,
            )
            slot_scores.append(
                SupportSlotScore(
                    slot_index=slot_index,
                    score=score,
                    region=region,
                    click_position=GameCoordinates.region_center(region),
                    template_path=template_path,
                    variant_name=variant_name,
                    component_scores=component_scores,
                )
            )
        return slot_scores

    def _offset_metric(
        self,
        slot_scores: list[SupportSlotScore],
    ) -> tuple[float, float]:
        ranked = sorted(slot_scores, key=lambda item: item.score, reverse=True)
        best_slot = ranked[0] if ranked else None
        second_slot = ranked[1] if len(ranked) > 1 else None
        peak_score = best_slot.score if best_slot else 0.0
        margin = peak_score - second_slot.score if best_slot and second_slot else peak_score
        return peak_score + margin, peak_score

    def _combine_component_scores(
        self,
        component_scores: dict[str, float],
        *,
        variant_names: tuple[str, ...] = TEMPLATE_VARIANTS,
    ) -> float:
        total_weight = sum(VARIANT_WEIGHTS[name] for name in variant_names)
        if total_weight <= 0:
            return 0.0
        score = sum(
            component_scores.get(name, 0.0) * VARIANT_WEIGHTS[name]
            for name in variant_names
        ) / total_weight
        return float(max(0.0, min(score, 1.0)))

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

    def _load_template(self, image_path: Path) -> np.ndarray:
        cached = self._image_cache.get(image_path)
        if cached is not None:
            return cached
        image = _read_image(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(f"无法读取助战模板：{image_path}")
        self._image_cache[image_path] = image
        return image

    def _load_mask(self, mask_path: Optional[Path]) -> Optional[np.ndarray]:
        if mask_path is None:
            return None
        cached = self._mask_cache.get(mask_path)
        if cached is not None:
            return cached
        mask = _read_image(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            return None
        self._mask_cache[mask_path] = mask
        return mask


def _load_generated_variants(generated_dir: Path) -> list[SupportTemplateVariant]:
    if not generated_dir.exists():
        return []
    templates: list[SupportTemplateVariant] = []
    for source_dir in sorted(item for item in generated_dir.iterdir() if item.is_dir()):
        for variant_name in TEMPLATE_VARIANTS:
            image_path = source_dir / f"{variant_name}.png"
            if not image_path.exists():
                continue
            mask_path = source_dir / f"{variant_name}_mask.png"
            templates.append(
                SupportTemplateVariant(
                    source_name=source_dir.name,
                    variant_name=variant_name,
                    image_path=image_path,
                    mask_path=mask_path if mask_path.exists() else None,
                )
            )
    return templates


def _template_generated_dir(generated_root: Path) -> Path:
    return generated_root / "template_matcher"


def _prepare_screen_gray(screen_rgb: np.ndarray) -> np.ndarray:
    if screen_rgb.ndim == 2:
        return screen_rgb
    if screen_rgb.shape[2] == 4:
        gray = cv2.cvtColor(screen_rgb, cv2.COLOR_BGRA2GRAY)
    else:
        gray = cv2.cvtColor(screen_rgb, cv2.COLOR_RGB2GRAY)
    return cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)


def _annotate_support_screen(
    screen_rgb: np.ndarray,
    analysis: SupportPortraitAnalysis,
) -> np.ndarray:
    if screen_rgb.ndim == 2:
        annotated = cv2.cvtColor(screen_rgb, cv2.COLOR_GRAY2BGR)
    else:
        annotated = cv2.cvtColor(screen_rgb, cv2.COLOR_RGB2BGR)
    strip_x1, strip_y1, strip_x2, strip_y2 = GameCoordinates.SUPPORT_PORTRAIT_STRIP
    cv2.rectangle(annotated, (strip_x1, strip_y1), (strip_x2, strip_y2), (255, 128, 0), 1)
    for item in analysis.slot_scores:
        x1, y1, x2, y2 = item.region
        color = (0, 255, 0) if analysis.best_slot and item.slot_index == analysis.best_slot.slot_index else (0, 128, 255)
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
    return annotated


def _read_image_rgb(image_path: Path) -> np.ndarray:
    image = _read_image(image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"无法读取截图：{image_path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _read_image(image_path: Path, flags: int) -> Optional[np.ndarray]:
    raw = np.fromfile(str(image_path), dtype=np.uint8)
    if raw.size == 0:
        return None
    return cv2.imdecode(raw, flags)


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


def _write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded, buffer = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError(f"无法写入 PNG：{path}")
    buffer.tofile(path)
