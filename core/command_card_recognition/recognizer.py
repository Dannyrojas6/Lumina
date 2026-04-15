"""普通指令卡归属识别。"""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations

import cv2
import numpy as np

from core.command_card_recognition.cropper import (
    CardCropper,
    crop_command_card_face,
    detect_command_card_color,
)
from core.command_card_recognition.layout import (
    COMMAND_CARD_SLOT_LAYOUTS,
    apply_local_masks,
    crop_absolute_region,
    crop_command_card_for_recognition,
)
from core.command_card_recognition.models import (
    CommandCardInfo,
    CommandCardAssignmentCandidate,
    CommandCardPrediction,
    CommandCardScore,
    CommandCardTrace,
)
from core.command_card_recognition.occlusion import OcclusionMaskBuilder
from core.command_card_recognition.part_encoder import PartFeatureEncoder
from core.command_card_recognition.parts import CardPartExtractor
from core.command_card_recognition.reference_cache import CommandCardReferenceCache
from core.command_card_recognition.scorer import CardScorer
from core.command_card_recognition.solver import HandAssignmentSolver
from core.shared.resource_catalog import ResourceCatalog
from core.shared.screen_coordinates import GameCoordinates
from core.support_recognition import PortraitEncoder

COMMAND_CARD_MIN_SCORE = 0.07
COMMAND_CARD_MIN_MARGIN = 0.002
COMMAND_CARD_NEGATIVE_PENALTY = 0.65
INFO_STRIP_TOP_RATIO = 24 / 170
INFO_STRIP_BOTTOM_RATIO = 62 / 170
COMMAND_CARD_ROUTE1_TIEBREAK_MARGIN = 0.01
COMMAND_CARD_ROUTE1_TIEBREAK_ADVANTAGE = 0.005
COMMAND_CARD_CHAIN_PRIORITY = {
    "support_attacker_same_servant": 0,
    "buster_3": 1,
    "arts_3": 2,
    "tri_color": 3,
    "other_same_servant": 4,
    "quick_3": 5,
    "mixed": 6,
}


def collect_command_card_reference_paths(
    resources: ResourceCatalog, servant_name: str
) -> list[str]:
    servant_dir = resources.servant_dir(servant_name)
    command_dir = servant_dir / "atlas" / "commands"
    if not command_dir.exists():
        return []
    return sorted(str(path) for path in command_dir.glob("**/*.png"))


def mask_command_card_info_strip(image_rgb: np.ndarray) -> np.ndarray:
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


def classify_card_chain(
    cards: tuple[CommandCardInfo, CommandCardInfo, CommandCardInfo],
    *,
    support_attacker: str | None = None,
) -> str:
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
        self.cropper = CardCropper()
        self.mask_builder = OcclusionMaskBuilder()
        self.part_extractor = CardPartExtractor()
        self.feature_encoder = PartFeatureEncoder(self.encoder)
        self.reference_cache = CommandCardReferenceCache(
            resources,
            encoder=self.encoder,
        )
        self.assignment_solver = HandAssignmentSolver()
        self.scorer = CardScorer(
            reference_cache=self.reference_cache,
            feature_encoder=self.feature_encoder,
            negative_penalty=self.negative_penalty,
        )

    def analyze_frontline(
        self,
        screen_rgb: np.ndarray,
        frontline_servants: list[str],
        support_attacker: str | None = None,
    ) -> CommandCardPrediction:
        normalized_frontline = [
            _normalize_servant_name(item)
            for item in frontline_servants
            if str(item).strip()
        ]
        normalized_support_attacker = _normalize_servant_name(support_attacker)
        traces: list[CommandCardTrace] = []
        for card_index in GameCoordinates.COMMAND_CARD_REGIONS:
            traces.append(
                self._analyze_card(
                    card_index=card_index,
                    screen_rgb=screen_rgb,
                    current_servants=normalized_frontline,
                    support_attacker=normalized_support_attacker,
                )
            )
        joint_result = self.assignment_solver.solve(
            traces,
            frontline_servants=normalized_frontline,
            support_attacker=normalized_support_attacker or None,
        )
        traces = self._apply_joint_assignment(
            traces,
            joint_result.owners_by_index,
        )
        return CommandCardPrediction(
            frontline_servants=normalized_frontline,
            support_attacker=normalized_support_attacker or None,
            traces=traces,
            min_score=self.min_score,
            min_margin=self.min_margin,
            joint_score=joint_result.joint_score,
            joint_margin=joint_result.joint_margin,
            joint_low_confidence=joint_result.joint_low_confidence,
            assignment_candidates=joint_result.assignment_candidates,
        )

    def recognize_frontline(
        self,
        screen_rgb: np.ndarray,
        frontline_servants: list[str],
        support_attacker: str | None = None,
    ) -> dict[int, str | None]:
        return self.analyze_frontline(
            screen_rgb,
            frontline_servants,
            support_attacker=support_attacker,
        ).owners

    def recognize_frontline_cards(
        self,
        screen_rgb: np.ndarray,
        frontline_servants: list[str],
        support_attacker: str | None = None,
    ) -> list[CommandCardInfo]:
        return self.analyze_frontline(
            screen_rgb,
            frontline_servants,
            support_attacker=support_attacker,
        ).cards

    def _analyze_card(
        self,
        *,
        card_index: int,
        screen_rgb: np.ndarray,
        current_servants: list[str],
        support_attacker: str,
    ) -> CommandCardTrace:
        crop = self.cropper.crop(screen_rgb, card_index)
        support_badge = bool(support_attacker and crop.support_badge)
        if crop.recognition_rgb.size == 0 or not current_servants:
            fallback_scores = (
                [
                    CommandCardScore(servant_name=support_attacker, score=1.0)
                ]
                if support_badge and support_attacker
                else []
            )
            return CommandCardTrace(
                index=card_index,
                owner=support_attacker if support_badge else None,
                color=crop.color,
                score=1.0 if support_badge else 0.0,
                margin=1.0 if support_badge else 0.0,
                support_badge=support_badge,
                low_confidence=not support_badge,
                scores=fallback_scores,
                crop_region_abs=crop.crop_region_abs,
                mask_rects_abs=[],
            )

        occlusion = self.mask_builder.build(
            crop.recognition_rgb,
            card_index=card_index,
            support_badge=support_badge,
        )
        parts = self.part_extractor.extract(
            card_index=card_index,
            card_color=crop.color,
            masked_rgb=occlusion.masked_rgb,
            visibility_mask=occlusion.visibility_mask,
            crop_region_abs=crop.crop_region_abs,
        )
        candidate_scores = self.scorer.score_card(
            card_index=card_index,
            card_color=crop.color,
            current_servants=current_servants,
            parts=parts,
            support_attacker=support_attacker or None,
            support_badge=support_badge,
        )
        candidate_scores = self._apply_route1_tiebreak(
            candidate_scores,
            card_index=card_index,
            card_color=crop.color,
        )
        best_score = candidate_scores[0].score if candidate_scores else 0.0
        second_score = candidate_scores[1].score if len(candidate_scores) > 1 else 0.0
        margin = best_score - second_score
        route1_margin = (
            candidate_scores[0].route1_score
            - max((item.route1_score for item in candidate_scores[1:]), default=0.0)
            if candidate_scores
            else 0.0
        )
        best_part_score = (
            max((item.score for item in candidate_scores[0].part_scores), default=0.0)
            if candidate_scores
            else 0.0
        )

        if support_badge:
            support_score = next(
                (
                    item.score
                    for item in candidate_scores
                    if item.servant_name == support_attacker
                ),
                best_score,
            )
            return CommandCardTrace(
                index=card_index,
                owner=support_attacker,
                color=crop.color,
                score=support_score,
                margin=margin,
                support_badge=True,
                low_confidence=False,
                scores=candidate_scores,
                crop_region_abs=crop.crop_region_abs,
                mask_rects_abs=occlusion.mask_rects_abs,
            )

        owner = candidate_scores[0].servant_name if candidate_scores else None
        best_valid_part_count = candidate_scores[0].valid_part_count if candidate_scores else 0
        effective_margin = route1_margin if best_score < second_score else margin
        low_confidence = (
            owner is None
            or (
                best_score < self.min_score
                and best_part_score < self.min_score
            )
            or effective_margin < self.min_margin
            or best_valid_part_count < 2
        )
        return CommandCardTrace(
            index=card_index,
            owner=None if low_confidence else owner,
            color=crop.color,
            score=best_score,
            margin=margin,
            support_badge=False,
            low_confidence=low_confidence,
            scores=candidate_scores,
            crop_region_abs=crop.crop_region_abs,
            mask_rects_abs=occlusion.mask_rects_abs,
        )

    def _apply_joint_assignment(
        self,
        traces: list[CommandCardTrace],
        owners_by_index: dict[int, str | None],
    ) -> list[CommandCardTrace]:
        updated: list[CommandCardTrace] = []
        for trace in traces:
            final_owner = owners_by_index.get(trace.index)
            selected_score = self._find_score(trace.scores, final_owner)
            if final_owner is None or selected_score is None:
                updated.append(replace(trace, owner=None))
                continue
            updated_margin = selected_score.score - max(
                (
                    score.score
                    for score in trace.scores
                    if score.servant_name != final_owner
                ),
                default=0.0,
            )
            updated.append(
                replace(
                    trace,
                    owner=final_owner,
                    score=selected_score.score,
                    margin=updated_margin,
                )
            )
        return updated

    @staticmethod
    def _find_score(
        scores: list[CommandCardScore],
        servant_name: str | None,
    ) -> CommandCardScore | None:
        for score in scores:
            if score.servant_name == servant_name:
                return score
        return None

    def _apply_route1_tiebreak(
        self,
        candidate_scores: list[CommandCardScore],
        *,
        card_index: int,
        card_color: str | None,
    ) -> list[CommandCardScore]:
        if card_index == 2 and card_color == "quick":
            return candidate_scores
        if len(candidate_scores) < 2:
            return candidate_scores
        top = candidate_scores[0]
        route1_leader = max(candidate_scores, key=lambda item: item.route1_score)
        if route1_leader.servant_name == top.servant_name:
            return candidate_scores
        if (top.score - route1_leader.score) > COMMAND_CARD_ROUTE1_TIEBREAK_MARGIN:
            return candidate_scores
        if (
            route1_leader.route1_score - top.route1_score
            <= COMMAND_CARD_ROUTE1_TIEBREAK_ADVANTAGE
        ):
            return candidate_scores
        reordered = [route1_leader]
        reordered.extend(
            item for item in candidate_scores if item.servant_name != route1_leader.servant_name
        )
        return reordered
