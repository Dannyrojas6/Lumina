"""普通指令卡归属识别。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np

from core.coordinates import GameCoordinates
from core.portrait_embedding import (
    PortraitEncoder,
    cosine_similarity,
    load_rgba_image,
    rgba_to_rgb_on_black,
)
from core.resources import ResourceCatalog

COMMAND_CARD_MIN_SCORE = 0.07
COMMAND_CARD_MIN_MARGIN = 0.002
COMMAND_CARD_NEGATIVE_PENALTY = 0.65
INFO_STRIP_TOP_RATIO = 24 / 170
INFO_STRIP_BOTTOM_RATIO = 62 / 170
COMMAND_CARD_CHAIN_PRIORITY = {
    "support_attacker_same_servant": 0,
    "buster_3": 1,
    "arts_3": 2,
    "tri_color": 3,
    "other_same_servant": 4,
    "quick_3": 5,
    "mixed": 6,
}


@dataclass(frozen=True)
class CommandCardInfo:
    """描述单张普通指令卡的归属和颜色。"""

    index: int
    owner: str | None
    color: str | None


def collect_command_card_reference_paths(
    resources: ResourceCatalog, servant_name: str
) -> list[str]:
    """返回单个从者 commands 目录下的全部 PNG。"""
    servant_dir = resources.servant_dir(servant_name)
    command_dir = servant_dir / "atlas" / "commands"
    if not command_dir.exists():
        return []
    return sorted(str(path) for path in command_dir.glob("**/*.png"))


def crop_command_card_face(
    screen_rgb: np.ndarray,
    region: tuple[int, int, int, int],
) -> np.ndarray:
    """只裁普通指令卡上半部分，用于归属识别。"""
    x1, y1, x2, y2 = region
    midpoint = y1 + ((y2 - y1) // 2)
    return screen_rgb[y1:midpoint, x1:x2].copy()


def crop_command_card_color_zone(card_rgb: np.ndarray) -> np.ndarray:
    """裁出普通卡下半部用于颜色判断的采样区。"""
    if card_rgb.size == 0:
        return card_rgb
    height, width = card_rgb.shape[:2]
    left_ratio, top_ratio, right_ratio, bottom_ratio = (
        GameCoordinates.COMMAND_CARD_COLOR_ZONE_RATIOS
    )
    x1 = max(0, min(int(round(width * left_ratio)), width))
    y1 = max(0, min(int(round(height * top_ratio)), height))
    x2 = max(x1, min(int(round(width * right_ratio)), width))
    y2 = max(y1, min(int(round(height * bottom_ratio)), height))
    return card_rgb[y1:y2, x1:x2].copy()


def detect_command_card_color(card_rgb: np.ndarray) -> str | None:
    """根据采样区主色判断普通卡颜色。"""
    sample = crop_command_card_color_zone(card_rgb)
    if sample.size == 0:
        return None
    mean_r, mean_g, mean_b = sample.reshape(-1, 3).mean(axis=0)
    if mean_b >= mean_g and mean_b >= mean_r:
        return "arts"
    if mean_g >= mean_r and mean_g >= mean_b:
        return "quick"
    return "buster"


def mask_command_card_info_strip(image_rgb: np.ndarray) -> np.ndarray:
    """遮掉上方信息横带，避开助战标签和同一水平线的 buff 信息。"""
    if image_rgb.size == 0:
        return image_rgb
    masked = image_rgb.copy()
    height = masked.shape[0]
    top = int(round(height * INFO_STRIP_TOP_RATIO))
    bottom = int(round(height * INFO_STRIP_BOTTOM_RATIO))
    top = max(0, min(top, height))
    bottom = max(top, min(bottom, height))
    if bottom <= top:
        return masked
    keep_mask = np.ones(masked.shape[:2], dtype=bool)
    keep_mask[top:bottom, :] = False
    if not np.any(keep_mask):
        masked[top:bottom, :] = 0
        return masked
    mean_color = masked[keep_mask].reshape(-1, 3).mean(axis=0)
    masked[top:bottom, :] = np.round(mean_color).astype(np.uint8)
    return masked


@dataclass(frozen=True)
class CommandCardMatch:
    """描述单张普通指令卡的识别结果。"""

    card_index: int
    owner: str | None
    score: float
    margin: float


def classify_card_chain(
    cards: tuple[CommandCardInfo, CommandCardInfo, CommandCardInfo],
    *,
    support_attacker: str | None = None,
) -> str:
    """判断三张普通卡属于哪种连携类型。"""
    owners = [card.owner for card in cards]
    colors = [card.color for card in cards]
    owner_set = {owner for owner in owners if owner}
    color_set = {color for color in colors if color}

    if len(owner_set) == 1 and len(owners) == 3 and owners[0] is not None:
        owner = owners[0]
        if support_attacker and owner == _normalize_servant_name(support_attacker):
            return "support_attacker_same_servant"
        return "other_same_servant"

    if len(color_set) == 1 and len(colors) == 3 and colors[0] is not None:
        if colors[0] == "buster":
            return "buster_3"
        if colors[0] == "arts":
            return "arts_3"
        if colors[0] == "quick":
            return "quick_3"

    if len(color_set) == 3:
        return "tri_color"

    return "mixed"


def choose_best_card_chain(
    *,
    cards: list[CommandCardInfo],
    servant_priority: list[str],
    support_attacker: str | None = None,
) -> list[CommandCardInfo]:
    """从五张普通卡中选出一组优先级最高的三张。"""
    normalized_priority = [
        _normalize_servant_name(item)
        for item in servant_priority
        if str(item).strip()
    ]
    normalized_support_attacker = (
        _normalize_servant_name(support_attacker) if support_attacker else None
    )
    if len(cards) <= 3:
        return sorted(cards, key=lambda item: item.index)

    ranked = sorted(
        combinations(cards, 3),
        key=lambda combo: _card_chain_sort_key(
            combo,
            servant_priority=normalized_priority,
            support_attacker=normalized_support_attacker,
        ),
    )
    return list(ranked[0]) if ranked else []


def _card_chain_sort_key(
    cards: tuple[CommandCardInfo, CommandCardInfo, CommandCardInfo],
    *,
    servant_priority: list[str],
    support_attacker: str | None,
) -> tuple[int, tuple[int, int, int], tuple[int, int, int]]:
    chain_type = classify_card_chain(cards, support_attacker=support_attacker)
    owner_ranks = sorted(
        _owner_priority_rank(card.owner, servant_priority) for card in cards
    )
    indices = tuple(sorted(card.index for card in cards))
    return (
        COMMAND_CARD_CHAIN_PRIORITY.get(chain_type, 999),
        tuple(owner_ranks),
        indices,
    )


def _owner_priority_rank(owner: str | None, servant_priority: list[str]) -> int:
    if not owner:
        return len(servant_priority) + 100
    normalized = _normalize_servant_name(owner)
    try:
        return servant_priority.index(normalized)
    except ValueError:
        return len(servant_priority) + 10


def _normalize_servant_name(value: str | None) -> str:
    return str(value or "").replace("\\", "/").strip().strip("/")


class CommandCardRecognizer:
    """根据前排从者的 commands 素材识别五张普通指令卡归属。"""

    def __init__(
        self,
        resources: ResourceCatalog,
        *,
        encoder: PortraitEncoder | None = None,
        min_score: float = COMMAND_CARD_MIN_SCORE,
        min_margin: float = COMMAND_CARD_MIN_MARGIN,
        negative_penalty: float = COMMAND_CARD_NEGATIVE_PENALTY,
    ) -> None:
        self.resources = resources
        self.encoder = encoder or PortraitEncoder(resources.portrait_encoder_model())
        self.min_score = min_score
        self.min_margin = min_margin
        self.negative_penalty = negative_penalty
        self._embedding_cache: dict[str, np.ndarray] = {}

    def recognize_frontline(
        self,
        screen_rgb: np.ndarray,
        frontline_servants: list[str],
    ) -> dict[int, str | None]:
        """识别五张普通指令卡分别属于谁。"""
        normalized_frontline = [
            str(item).replace("\\", "/").strip().strip("/")
            for item in frontline_servants
            if str(item).strip()
        ]
        if not normalized_frontline:
            return {index: None for index in GameCoordinates.COMMAND_CARD_REGIONS}

        servant_vectors = {
            servant_name: self._command_vectors(servant_name)
            for servant_name in normalized_frontline
        }
        results: dict[int, str | None] = {}
        for card_index, region in GameCoordinates.COMMAND_CARD_REGIONS.items():
            crop = crop_command_card_face(screen_rgb, region)
            if crop.size == 0:
                results[card_index] = None
                continue
            query_vector = self.encoder.encode(mask_command_card_info_strip(crop))
            results[card_index] = self._match_owner(
                query_vector=query_vector,
                current_servants=normalized_frontline,
                servant_vectors=servant_vectors,
            ).owner
        return results

    def recognize_frontline_cards(
        self,
        screen_rgb: np.ndarray,
        frontline_servants: list[str],
    ) -> list[CommandCardInfo]:
        """识别五张普通卡的归属和颜色。"""
        owners = self.recognize_frontline(screen_rgb, frontline_servants)
        cards: list[CommandCardInfo] = []
        for card_index, region in GameCoordinates.COMMAND_CARD_REGIONS.items():
            x1, y1, x2, y2 = region
            card_rgb = screen_rgb[y1:y2, x1:x2].copy()
            cards.append(
                CommandCardInfo(
                    index=card_index,
                    owner=owners.get(card_index),
                    color=detect_command_card_color(card_rgb),
                )
            )
        return cards

    def _command_vectors(self, servant_name: str) -> np.ndarray:
        if servant_name in self._embedding_cache:
            return self._embedding_cache[servant_name]

        image_paths = collect_command_card_reference_paths(self.resources, servant_name)
        images = [
            mask_command_card_info_strip(
                rgba_to_rgb_on_black(load_rgba_image(image_path))
            )
            for image_path in image_paths
        ]
        vectors = self.encoder.encode_batch(images)
        self._embedding_cache[servant_name] = vectors
        return vectors

    def _match_owner(
        self,
        *,
        query_vector: np.ndarray,
        current_servants: list[str],
        servant_vectors: dict[str, np.ndarray],
    ) -> CommandCardMatch:
        scored: list[tuple[str, float]] = []
        for servant_name in current_servants:
            positive_vectors = servant_vectors.get(servant_name)
            if positive_vectors is None or positive_vectors.size == 0:
                continue
            negative_vectors = [
                servant_vectors[item]
                for item in current_servants
                if item != servant_name and servant_vectors[item].size > 0
            ]
            positive_score = float(
                cosine_similarity(query_vector, positive_vectors).max(initial=0.0)
            )
            if negative_vectors:
                negative_score = float(
                    cosine_similarity(
                        query_vector,
                        np.concatenate(negative_vectors, axis=0),
                    ).max(initial=0.0)
                )
            else:
                negative_score = 0.0
            scored.append(
                (
                    servant_name,
                    positive_score - (self.negative_penalty * negative_score),
                )
            )

        if not scored:
            return CommandCardMatch(card_index=0, owner=None, score=0.0, margin=0.0)

        scored.sort(key=lambda item: item[1], reverse=True)
        best_name, best_score = scored[0]
        second_score = scored[1][1] if len(scored) > 1 else 0.0
        margin = best_score - second_score
        if best_score < self.min_score or margin < self.min_margin:
            return CommandCardMatch(
                card_index=0,
                owner=None,
                score=best_score,
                margin=margin,
            )
        return CommandCardMatch(
            card_index=0,
            owner=best_name,
            score=best_score,
            margin=margin,
        )
