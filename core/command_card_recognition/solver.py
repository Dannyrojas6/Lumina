"""普通指令卡整手联合判定。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from core.command_card_recognition.models import (
    CommandCardAssignmentCandidate,
    CommandCardTrace,
)

COMMAND_CARD_JOINT_MIN_MARGIN = 0.005
COMMAND_CARD_JOINT_PROMOTED_RANK_BONUS = 0.006


@dataclass(frozen=True)
class HandAssignmentResult:
    owners_by_index: dict[int, str | None]
    joint_score: float
    joint_margin: float
    joint_low_confidence: bool
    assignment_candidates: list[CommandCardAssignmentCandidate]


class HandAssignmentSolver:
    """在当前前排三候选下，为整手五张卡统一选取归属。"""

    def __init__(self, *, joint_min_margin: float = COMMAND_CARD_JOINT_MIN_MARGIN) -> None:
        self.joint_min_margin = joint_min_margin

    def solve(
        self,
        traces: list[CommandCardTrace],
        *,
        frontline_servants: list[str],
        support_attacker: str | None,
    ) -> HandAssignmentResult:
        if not traces:
            return HandAssignmentResult(
                owners_by_index={},
                joint_score=0.0,
                joint_margin=0.0,
                joint_low_confidence=True,
                assignment_candidates=[],
            )

        domains = [
            self._candidate_domain(
                trace,
                frontline_servants=frontline_servants,
                support_attacker=support_attacker,
            )
            for trace in traces
        ]
        if any(not domain for domain in domains):
            return HandAssignmentResult(
                owners_by_index={},
                joint_score=0.0,
                joint_margin=0.0,
                joint_low_confidence=True,
                assignment_candidates=[],
            )

        score_maps = [
            {score.servant_name: score.score for score in trace.scores}
            for trace in traces
        ]
        raw_candidates: list[tuple[dict[int, str | None], float]] = []
        for assigned_servants in product(*domains):
            owners_by_index: dict[int, str | None] = {}
            joint_score_raw = 0.0
            legal = True
            for trace, score_map, servant_name in zip(
                traces, score_maps, assigned_servants, strict=True
            ):
                if servant_name not in score_map:
                    legal = False
                    break
                owners_by_index[trace.index] = servant_name
                joint_score_raw += self._adjusted_card_score(trace, servant_name)
            if legal:
                raw_candidates.append((owners_by_index, joint_score_raw))

        if not raw_candidates:
            return HandAssignmentResult(
                owners_by_index={},
                joint_score=0.0,
                joint_margin=0.0,
                joint_low_confidence=True,
                assignment_candidates=[],
            )

        raw_candidates.sort(key=lambda item: item[1], reverse=True)
        denominator = max(1, len(traces))
        best_owners, best_raw = raw_candidates[0]
        second_raw = raw_candidates[1][1] if len(raw_candidates) > 1 else 0.0
        joint_score = best_raw / denominator
        joint_margin = (
            (best_raw - second_raw)
            if len(raw_candidates) > 1
            else joint_score
        )
        assignment_candidates = [
            CommandCardAssignmentCandidate(
                owners_by_index=owners,
                score=raw_score / denominator,
                margin_from_best=(best_raw - raw_score),
            )
            for owners, raw_score in raw_candidates[:2]
        ]
        return HandAssignmentResult(
            owners_by_index=best_owners,
            joint_score=joint_score,
            joint_margin=joint_margin,
            joint_low_confidence=joint_margin < self.joint_min_margin,
            assignment_candidates=assignment_candidates,
        )

    def _adjusted_card_score(
        self,
        trace: CommandCardTrace,
        servant_name: str,
    ) -> float:
        score_map = {score.servant_name: score.score for score in trace.scores}
        value = score_map[servant_name]
        if not trace.scores:
            return value
        top_ranked = trace.scores[0]
        max_score = max(score.score for score in trace.scores)
        if servant_name == top_ranked.servant_name and top_ranked.score < max_score:
            value += (max_score - top_ranked.score) + COMMAND_CARD_JOINT_PROMOTED_RANK_BONUS
        return value

    def _candidate_domain(
        self,
        trace: CommandCardTrace,
        *,
        frontline_servants: list[str],
        support_attacker: str | None,
    ) -> list[str]:
        if trace.support_badge:
            return [support_attacker] if support_attacker else []
        domain: list[str] = []
        for score in trace.scores:
            if score.servant_name in frontline_servants and score.servant_name not in domain:
                domain.append(score.servant_name)
        return domain
