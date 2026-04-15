import unittest

from core.command_card_recognition import (
    CommandCardAssignmentCandidate,
    CommandCardScore,
    CommandCardTrace,
)
from core.command_card_recognition.solver import (
    COMMAND_CARD_JOINT_MIN_MARGIN,
    HandAssignmentSolver,
)


def _score(servant_name: str, score: float) -> CommandCardScore:
    return CommandCardScore(servant_name=servant_name, score=score)


def _trace(
    index: int,
    *,
    scores: list[CommandCardScore],
    support_badge: bool = False,
) -> CommandCardTrace:
    return CommandCardTrace(
        index=index,
        owner=scores[0].servant_name if scores else None,
        color="arts",
        score=scores[0].score if scores else 0.0,
        margin=(scores[0].score - scores[1].score) if len(scores) > 1 else 0.0,
        support_badge=support_badge,
        low_confidence=False,
        scores=scores,
    )


class CommandCardSolverTest(unittest.TestCase):
    def test_solver_finds_best_assignment_with_support_badge_constraint(self) -> None:
        solver = HandAssignmentSolver()
        traces = [
            _trace(
                1,
                scores=[
                    _score("caster/zhuge_liang", 0.22),
                    _score("caster/merlin", 0.15),
                    _score("berserker/morgan", 0.11),
                ],
            ),
            _trace(
                2,
                scores=[
                    _score("caster/merlin", 0.24),
                    _score("caster/zhuge_liang", 0.17),
                    _score("berserker/morgan", 0.10),
                ],
                support_badge=True,
            ),
            _trace(
                3,
                scores=[
                    _score("berserker/morgan", 0.28),
                    _score("caster/merlin", 0.18),
                    _score("caster/zhuge_liang", 0.12),
                ],
            ),
        ]

        result = solver.solve(
            traces,
            frontline_servants=[
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="caster/merlin",
        )

        self.assertFalse(result.joint_low_confidence)
        self.assertEqual(
            result.owners_by_index,
            {
                1: "caster/zhuge_liang",
                2: "caster/merlin",
                3: "berserker/morgan",
            },
        )
        self.assertGreater(result.joint_margin, COMMAND_CARD_JOINT_MIN_MARGIN)
        self.assertGreaterEqual(len(result.assignment_candidates), 2)

    def test_solver_marks_joint_low_confidence_when_margin_too_small(self) -> None:
        solver = HandAssignmentSolver()
        traces = [
            _trace(
                1,
                scores=[
                    _score("caster/zhuge_liang", 0.21),
                    _score("caster/merlin", 0.209),
                    _score("berserker/morgan", 0.05),
                ],
            ),
            _trace(
                2,
                scores=[
                    _score("caster/merlin", 0.22),
                    _score("caster/zhuge_liang", 0.219),
                    _score("berserker/morgan", 0.04),
                ],
            ),
        ]

        result = solver.solve(
            traces,
            frontline_servants=[
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        self.assertTrue(result.joint_low_confidence)
        self.assertLess(result.joint_margin, COMMAND_CARD_JOINT_MIN_MARGIN)

    def test_solver_marks_joint_low_confidence_when_no_assignment_is_legal(self) -> None:
        solver = HandAssignmentSolver()
        traces = [
            _trace(
                1,
                scores=[
                    _score("caster/zhuge_liang", 0.20),
                    _score("caster/merlin", 0.18),
                ],
                support_badge=True,
            )
        ]

        result = solver.solve(
            traces,
            frontline_servants=[
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        self.assertTrue(result.joint_low_confidence)
        self.assertEqual(result.owners_by_index, {})
        self.assertEqual(result.assignment_candidates, [])
