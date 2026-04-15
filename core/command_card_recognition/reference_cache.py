"""普通指令卡参考图缓存。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from core.command_card_recognition.layout import (
    COMMAND_CARD_SLOT_LAYOUTS,
    part_layouts_for_slot,
)
from core.command_card_recognition.occlusion import OcclusionMaskBuilder
from core.command_card_recognition.part_encoder import PartFeatureEncoder, edge_vector, gray_vector
from core.command_card_recognition.parts import CardPartExtractor
from core.shared.resource_catalog import ResourceCatalog
from core.support_recognition import (
    PortraitEncoder,
    load_rgba_image,
    rgba_to_rgb_on_black,
)


@dataclass(frozen=True)
class ReferencePartBank:
    """描述单个从者单个 patch 的参考特征库。"""

    embeddings: np.ndarray
    gray_vectors: np.ndarray
    edge_vectors: np.ndarray


class CommandCardReferenceCache:
    """缓存从者普通卡参考图的局部特征。"""

    def __init__(
        self,
        resources: ResourceCatalog,
        *,
        encoder: PortraitEncoder,
    ) -> None:
        self.resources = resources
        self.encoder = encoder
        self._mask_builder = OcclusionMaskBuilder()
        self._part_extractor = CardPartExtractor()
        self._feature_encoder = PartFeatureEncoder(encoder)
        self._cache: dict[tuple[str, int], dict[str, ReferencePartBank]] = {}

    def banks_for_slot(self, servant_name: str, card_index: int) -> dict[str, ReferencePartBank]:
        cache_key = (servant_name, card_index)
        if cache_key in self._cache:
            return self._cache[cache_key]

        image_paths = self._collect_reference_paths(servant_name)
        slot_layout = COMMAND_CARD_SLOT_LAYOUTS[card_index]
        width = slot_layout.crop_region_abs[2] - slot_layout.crop_region_abs[0]
        height = slot_layout.crop_region_abs[3] - slot_layout.crop_region_abs[1]

        part_images: dict[str, list[np.ndarray]] = {
            layout.name: [] for layout in part_layouts_for_slot(card_index)
        }
        for image_path in image_paths:
            reference_rgb = rgba_to_rgb_on_black(load_rgba_image(image_path))
            resized = cv2.resize(
                reference_rgb,
                (width, height),
                interpolation=cv2.INTER_AREA,
            )
            masked = self._mask_builder.build(
                resized,
                card_index=card_index,
                support_badge=False,
            )
            parts = self._part_extractor.extract(
                card_index=card_index,
                card_color=None,
                masked_rgb=masked.masked_rgb,
                visibility_mask=masked.visibility_mask,
                crop_region_abs=slot_layout.crop_region_abs,
            )
            for part in parts:
                if part.valid:
                    part_images[part.part_name].append(part.image_rgb)

        banks: dict[str, ReferencePartBank] = {}
        for part_name, images in part_images.items():
            if not images:
                banks[part_name] = ReferencePartBank(
                    embeddings=np.empty((0, 128), dtype=np.float32),
                    gray_vectors=np.empty((0, 0), dtype=np.float32),
                    edge_vectors=np.empty((0, 0), dtype=np.float32),
                )
                continue
            banks[part_name] = ReferencePartBank(
                embeddings=self.encoder.encode_batch(images),
                gray_vectors=np.stack([gray_vector(item) for item in images], axis=0),
                edge_vectors=np.stack([edge_vector(item) for item in images], axis=0),
            )
        self._cache[cache_key] = banks
        return banks

    def _collect_reference_paths(self, servant_name: str) -> list[str]:
        servant_dir = self.resources.servant_dir(servant_name)
        command_dir = servant_dir / "atlas" / "commands"
        if not command_dir.exists():
            return []
        return sorted(str(path) for path in command_dir.glob("**/*.png"))
