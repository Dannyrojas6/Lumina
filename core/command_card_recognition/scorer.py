"""普通指令卡单卡评分。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.command_card_recognition.models import CommandCardPartScore, CommandCardScore
from core.command_card_recognition.part_encoder import (
    PartFeatureEncoder,
    normalized_similarity,
)
from core.command_card_recognition.parts import CommandCardPartObservation
from core.command_card_recognition.reference_cache import CommandCardReferenceCache, ReferencePartBank
from core.support_recognition import cosine_similarity


@dataclass(frozen=True)
class CardScoreResult:
    """描述单张卡的候选评分结果。"""

    scores: list[CommandCardScore]


class CardScorer:
    """为单张普通卡生成候选从者分数表。"""

    def __init__(
        self,
        *,
        reference_cache: CommandCardReferenceCache,
        feature_encoder: PartFeatureEncoder,
        negative_penalty: float,
    ) -> None:
        self.reference_cache = reference_cache
        self.feature_encoder = feature_encoder
        self.negative_penalty = negative_penalty

    def score_card(
        self,
        *,
        card_index: int,
        card_color: str | None,
        current_servants: list[str],
        parts: list[CommandCardPartObservation],
        support_attacker: str | None = None,
        support_badge: bool = False,
    ) -> list[CommandCardScore]:
        part_features = {
            part.part_name: self.feature_encoder.encode_query(part)
            for part in parts
            if part.valid
        }
        reference_banks = {
            servant_name: self.reference_cache.banks_for_slot(servant_name, card_index)
            for servant_name in current_servants
        }
        scored: list[CommandCardScore] = []
        for servant_name in current_servants:
            part_scores: list[CommandCardPartScore] = []
            weighted_score = 0.0
            weighted_route1 = 0.0
            weighted_route2 = 0.0
            visible_weight_sum = 0.0
            best_part_score = 0.0
            for part in parts:
                if not part.valid or part.part_name not in part_features:
                    continue
                route1, route2, gray_score, edge_score = self._score_part(
                    part_name=part.part_name,
                    query_features=part_features[part.part_name],
                    servant_name=servant_name,
                    current_servants=current_servants,
                    reference_banks=reference_banks,
                )
                score = (0.9 * route1) + (0.1 * route2)
                part_scores.append(
                    CommandCardPartScore(
                        part_name=part.part_name,
                        score=score,
                        route1_score=route1,
                        route2_score=route2,
                        gray_score=gray_score,
                        edge_score=edge_score,
                        visible_ratio=part.visible_ratio,
                        texture_score=part.texture_score,
                        weight=part.weight,
                        bbox_local=part.bbox_local,
                        bbox_abs=part.bbox_abs,
                    )
                )
                weighted_score += score * part.weight
                weighted_route1 += route1 * part.weight
                weighted_route2 += route2 * part.weight
                visible_weight_sum += part.weight
                best_part_score = max(best_part_score, score)
            mean_score = weighted_score / visible_weight_sum if visible_weight_sum > 0 else 0.0
            best_part_bonus_weight = self._best_part_bonus_weight(
                card_index=card_index,
                card_color=card_color,
            )
            final_score = (
                ((1.0 - best_part_bonus_weight) * mean_score)
                + (best_part_bonus_weight * best_part_score)
            )
            if support_attacker and not support_badge and servant_name == support_attacker:
                final_score -= 0.04
            scored.append(
                CommandCardScore(
                    servant_name=servant_name,
                    score=final_score,
                    route1_score=(
                        weighted_route1 / visible_weight_sum if visible_weight_sum > 0 else 0.0
                    ),
                    route2_score=(
                        weighted_route2 / visible_weight_sum if visible_weight_sum > 0 else 0.0
                    ),
                    valid_part_count=len(part_scores),
                    visible_weight_sum=visible_weight_sum,
                    part_scores=part_scores,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored

    def _score_part(
        self,
        *,
        part_name: str,
        query_features,
        servant_name: str,
        current_servants: list[str],
        reference_banks: dict[str, dict[str, ReferencePartBank]],
    ) -> tuple[float, float, float, float]:
        positive_bank = reference_banks[servant_name].get(part_name)
        if positive_bank is None:
            return (0.0, 0.0, 0.0, 0.0)
        negative_banks = [
            reference_banks[item][part_name]
            for item in current_servants
            if item != servant_name and part_name in reference_banks[item]
        ]

        positive_embed = self._max_embedding_similarity(
            query_features.embedding, positive_bank.embeddings
        )
        negative_embed = self._max_embedding_similarity(
            query_features.embedding,
            self._concat_embeddings(negative_banks),
        )
        route1 = positive_embed - (self.negative_penalty * negative_embed)

        gray_positive = self._max_vector_similarity(
            query_features.gray_vector,
            positive_bank.gray_vectors,
        )
        gray_score = gray_positive

        edge_positive = self._max_vector_similarity(
            query_features.edge_vector,
            positive_bank.edge_vectors,
        )
        edge_score = edge_positive
        route2 = (0.6 * gray_score) + (0.4 * edge_score)
        return (route1, route2, gray_score, edge_score)

    def _max_embedding_similarity(
        self,
        query_vector: np.ndarray,
        bank: np.ndarray,
    ) -> float:
        if bank.size == 0:
            return 0.0
        return float(cosine_similarity(query_vector, bank).max(initial=0.0))

    def _max_vector_similarity(
        self,
        query_vector: np.ndarray,
        bank: np.ndarray,
    ) -> float:
        if query_vector.size == 0 or bank.size == 0:
            return 0.0
        return float(normalized_similarity(query_vector, bank).max(initial=0.0))

    def _concat_embeddings(self, banks: list[ReferencePartBank]) -> np.ndarray:
        arrays = [item.embeddings for item in banks if item.embeddings.size > 0]
        if not arrays:
            return np.empty((0, 128), dtype=np.float32)
        return np.concatenate(arrays, axis=0)

    def _concat_vectors(
        self,
        banks: list[ReferencePartBank],
        field_name: str,
    ) -> np.ndarray:
        arrays = [
            getattr(item, field_name)
            for item in banks
            if getattr(item, field_name).size > 0
        ]
        if not arrays:
            return np.empty((0, 0), dtype=np.float32)
        return np.concatenate(arrays, axis=0)

    def _best_part_bonus_weight(
        self,
        *,
        card_index: int,
        card_color: str | None,
    ) -> float:
        # Slot-2 quick cards have a recurring failure mode where one silhouette patch
        # can overpower stronger face/torso evidence. Keep those cards on the mean score.
        if card_index == 2 and card_color == "quick":
            return 0.0
        return 0.25
