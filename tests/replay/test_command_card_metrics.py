import unittest

from core.command_card_recognition import (
    CommandCardPrediction,
    CommandCardSample,
    CommandCardScore,
    CommandCardTrace,
    load_command_card_samples,
)
from scripts.evaluate_command_cards import compute_metrics


def _make_prediction() -> CommandCardPrediction:
    traces = [
        CommandCardTrace(
            index=1,
            owner="caster/zhuge_liang",
            color="arts",
            score=0.21,
            margin=0.05,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore("caster/zhuge_liang", 0.21),
                CommandCardScore("caster/merlin", 0.10),
                CommandCardScore("berserker/morgan", 0.06),
            ],
        ),
        CommandCardTrace(
            index=2,
            owner="caster/merlin",
            color="quick",
            score=0.20,
            margin=0.03,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore("caster/merlin", 0.20),
                CommandCardScore("caster/zhuge_liang", 0.17),
                CommandCardScore("berserker/morgan", 0.09),
            ],
        ),
        CommandCardTrace(
            index=3,
            owner="berserker/morgan",
            color="buster",
            score=0.25,
            margin=0.06,
            support_badge=True,
            low_confidence=False,
            scores=[
                CommandCardScore("berserker/morgan", 0.25),
                CommandCardScore("caster/merlin", 0.08),
                CommandCardScore("caster/zhuge_liang", 0.05),
            ],
        ),
        CommandCardTrace(
            index=4,
            owner="caster/zhuge_liang",
            color="arts",
            score=0.19,
            margin=0.02,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore("caster/zhuge_liang", 0.19),
                CommandCardScore("caster/merlin", 0.15),
                CommandCardScore("berserker/morgan", 0.07),
            ],
        ),
        CommandCardTrace(
            index=5,
            owner="caster/merlin",
            color="quick",
            score=0.23,
            margin=0.05,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore("caster/merlin", 0.23),
                CommandCardScore("caster/zhuge_liang", 0.12),
                CommandCardScore("berserker/morgan", 0.08),
            ],
        ),
    ]
    return CommandCardPrediction(
        frontline_servants=[
            "caster/zhuge_liang",
            "caster/merlin",
            "berserker/morgan",
        ],
        support_attacker="berserker/morgan",
        traces=traces,
        min_score=0.07,
        min_margin=0.002,
    )


class CommandCardMetricsTest(unittest.TestCase):
    def test_load_command_card_samples_includes_catalog_metadata(self) -> None:
        samples = load_command_card_samples()

        self.assertTrue(all(sample.occlusion_level for sample in samples))
        self.assertTrue(all(sample.source for sample in samples))
        self.assertTrue(
            any("merlin_vs_zhuge" in sample.hard_negative_tags for sample in samples)
        )

    def test_compute_metrics_summarizes_accuracy_and_hard_negative_groups(self) -> None:
        sample = CommandCardSample(
            image="dummy.png",
            frontline=[
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
            owners=[
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
                "caster/zhuge_liang",
                "caster/merlin",
            ],
            note="",
            occlusion_level="heavy",
            hard_negative_tags=["merlin_vs_zhuge"],
            source="manual",
        )

        metrics = compute_metrics([(sample, _make_prediction())])

        self.assertEqual(metrics["sample_count"], 1)
        self.assertEqual(metrics["card_accuracy"], 1.0)
        self.assertEqual(metrics["hand_accuracy"], 1.0)
        self.assertIn("heavy", metrics["occlusion_levels"])
        self.assertIn("merlin_vs_zhuge", metrics["hard_negative"])
