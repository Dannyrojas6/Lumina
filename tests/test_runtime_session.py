import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from core.command_card_recognition import (
    CommandCardPartScore,
    CommandCardPrediction,
    CommandCardScore,
    CommandCardTrace,
)
from core.runtime.session import RuntimeSession
from core.shared.resource_catalog import ResourceCatalog


def _make_prediction() -> CommandCardPrediction:
    traces = [
        CommandCardTrace(
            index=index,
            owner="caster/zhuge_liang" if index != 3 else "caster/merlin",
            color="arts",
            score=0.2,
            margin=0.1,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore(
                    "caster/zhuge_liang",
                    0.2,
                    route1_score=0.14,
                    route2_score=0.09,
                    valid_part_count=3,
                    visible_weight_sum=1.0,
                    part_scores=[
                        CommandCardPartScore(
                            part_name="center_face",
                            score=0.18,
                            route1_score=0.12,
                            route2_score=0.10,
                            gray_score=0.09,
                            edge_score=0.11,
                            visible_ratio=0.95,
                            texture_score=0.8,
                            weight=0.76,
                            bbox_local=(40, 40, 120, 120),
                            bbox_abs=(120, 655, 200, 735),
                        )
                    ],
                ),
                CommandCardScore("caster/merlin", 0.1),
                CommandCardScore("berserker/morgan", 0.0),
            ],
            crop_region_abs=(80 + (index * 10), 615, 312 + (index * 10), 905),
            mask_rects_abs=[
                (81 + (index * 10), 621, 312 + (index * 10), 657),
            ],
        )
        for index in range(1, 6)
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


class RuntimeSessionCommandCardEvidenceTest(unittest.TestCase):
    def test_save_command_card_evidence_writes_masked_preview(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            session = object.__new__(RuntimeSession)
            session.resources = ResourceCatalog(command_card_debug_dir=tmp_dir)
            session.last_current_turn = 2
            session.last_wave_index = 1
            session.loop_done = 0
            screen_rgb = np.zeros((1080, 1920, 3), dtype=np.uint8)
            prediction = _make_prediction()

            image_path, masked_path, json_path = RuntimeSession.save_command_card_evidence(
                session,
                prediction,
                screen_rgb,
            )

            self.assertTrue(Path(image_path).exists())
            self.assertTrue(Path(masked_path).exists())
            self.assertTrue(Path(json_path).exists())
            self.assertTrue(masked_path.endswith("_masked.png"))
            self.assertEqual(Path(image_path).parent.name, Path(masked_path).parent.name)
            self.assertEqual(Path(image_path).parent.name, Path(json_path).parent.name)
            self.assertRegex(Path(image_path).parent.name, r"^\d{8}$")
            parts_path = Path(json_path.replace(".json", "_parts.png"))
            self.assertTrue(parts_path.exists())

            with Path(json_path).open("r", encoding="utf-8") as file:
                payload = json.load(file)
            self.assertEqual(payload["masked_preview_path"], masked_path)
            self.assertEqual(payload["parts_preview_path"], str(parts_path))


if __name__ == "__main__":
    unittest.main()
