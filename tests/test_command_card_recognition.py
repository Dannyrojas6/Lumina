import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from core.command_card_recognition import (
    CommandCardAssignmentCandidate,
    CommandCardPrediction,
    CommandCardRecognizer,
    CommandCardPartScore,
    CommandCardScore,
    CommandCardTrace,
    collect_command_card_reference_paths,
    crop_command_card_face,
    crop_command_card_for_recognition,
    mask_command_card_info_strip,
    write_masked_preview_image,
    write_part_preview_image,
)
from core.support_recognition import load_rgb_image
from core.shared.resource_catalog import ResourceCatalog
from core.shared.screen_coordinates import GameCoordinates

TEST_IMAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "test_image"
    / "fight"
    / "指令卡梅林摩根诸葛亮.png"
)
FAILED_IMAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "test_image"
    / "fight"
    / "指令卡识别失败1.png"
)
FAILED_IMAGE_PATH_2 = (
    Path(__file__).resolve().parents[1]
    / "test_image"
    / "fight"
    / "指令卡识别失败2.png"
)
FAILED_IMAGE_PATH_3 = (
    Path(__file__).resolve().parents[1]
    / "test_image"
    / "fight"
    / "指令卡识别失败3.png"
)
FAILED_IMAGE_PATH_4 = (
    Path(__file__).resolve().parents[1]
    / "test_image"
    / "fight"
    / "指令卡识别失败4.png"
)
FAILED_IMAGE_PATH_5 = (
    Path(__file__).resolve().parents[1]
    / "test_image"
    / "fight"
    / "指令卡识别失败5.png"
)
COMMAND_CARD_DEBUG_DIR = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "screenshots"
    / "command_cards"
)
RUNTIME_EVIDENCE_FAILED_SLOT2_QUICK_1 = "command_cards_20260414_093541_852.png"
RUNTIME_EVIDENCE_FAILED_SLOT2_QUICK_2 = "command_cards_20260414_093620_670.png"


def _find_command_card_debug_file(filename: str) -> Path:
    matches = list(COMMAND_CARD_DEBUG_DIR.rglob(filename))
    if not matches:
        raise FileNotFoundError(filename)
    return matches[0]


class CommandCardRecognitionTest(unittest.TestCase):
    def test_crop_command_card_face_uses_upper_half_only(self) -> None:
        screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
        x1, y1, x2, y2 = GameCoordinates.COMMAND_CARD_REGIONS[1]
        midpoint = y1 + ((y2 - y1) // 2)
        screen[y1:midpoint, x1:x2] = 255
        screen[midpoint:y2, x1:x2] = [255, 0, 0]

        crop = crop_command_card_face(screen, GameCoordinates.COMMAND_CARD_REGIONS[1])

        self.assertEqual(crop.shape, (midpoint - y1, x2 - x1, 3))
        self.assertTrue(np.all(crop == 255))

    def test_collect_command_card_reference_paths_reads_servant_commands(self) -> None:
        resources = ResourceCatalog()

        altria_paths = collect_command_card_reference_paths(
            resources, "caster/altria_caster"
        )
        morgan_paths = collect_command_card_reference_paths(
            resources, "berserker/morgan"
        )

        self.assertEqual(len(altria_paths), 3)
        self.assertEqual(len(morgan_paths), 4)
        self.assertTrue(all(Path(path).suffix.lower() == ".png" for path in altria_paths))

    def test_mask_command_card_info_strip_only_neutralizes_horizontal_band(self) -> None:
        crop = np.zeros((170, 270, 3), dtype=np.uint8)
        crop[:24, :] = 32
        crop[24:62, :] = 255
        crop[62:, :] = 96

        masked = mask_command_card_info_strip(crop)

        self.assertEqual(masked.shape, crop.shape)
        self.assertTrue(np.all(masked[:24, :] == 32))
        self.assertTrue(np.all(masked[62:, :] == 96))
        self.assertFalse(np.all(masked[24:62, :] == 255))

    def test_recognize_frontline_matches_merlin_morgan_zhuge_sample(self) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)
        from core.support_recognition import load_rgb_image

        screen = load_rgb_image(TEST_IMAGE_PATH)
        owners = recognizer.recognize_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        self.assertEqual(
            owners,
            {
                1: "berserker/morgan",
                2: "berserker/morgan",
                3: "caster/zhuge_liang",
                4: "caster/merlin",
                5: "caster/merlin",
            },
        )

    def test_recognize_frontline_masks_top_right_tag_on_morgan_card(self) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)
        from core.support_recognition import load_rgb_image

        screen = load_rgb_image(FAILED_IMAGE_PATH)
        owners = recognizer.recognize_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        self.assertEqual(
            owners,
            {
                1: "caster/zhuge_liang",
                2: "caster/merlin",
                3: "berserker/morgan",
                4: "caster/zhuge_liang",
                5: "caster/zhuge_liang",
            },
        )

    def test_recognize_frontline_prefers_support_attacker_view_on_tagged_cards(
        self,
    ) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)
        from core.support_recognition import load_rgb_image

        screen = load_rgb_image(FAILED_IMAGE_PATH_2)
        owners = recognizer.recognize_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        self.assertEqual(
            owners,
            {
                1: "caster/zhuge_liang",
                2: "caster/zhuge_liang",
                3: "berserker/morgan",
                4: "berserker/morgan",
                5: "berserker/morgan",
            },
        )

    def test_recognize_frontline_keeps_support_attacker_in_non_badge_candidates(
        self,
    ) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)
        from core.support_recognition import load_rgb_image

        screen = load_rgb_image(FAILED_IMAGE_PATH_3)
        owners = recognizer.recognize_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        self.assertEqual(
            owners,
            {
                1: "caster/merlin",
                2: "caster/merlin",
                3: "berserker/morgan",
                4: "caster/zhuge_liang",
                5: "caster/merlin",
            },
        )

    def test_analyze_frontline_returns_trace_and_scores(self) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)

        screen = load_rgb_image(FAILED_IMAGE_PATH_4)
        prediction = recognizer.analyze_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        self.assertEqual(
            prediction.owners,
            {
                1: "caster/zhuge_liang",
                2: "caster/zhuge_liang",
                3: "caster/merlin",
                4: "caster/zhuge_liang",
                5: "caster/merlin",
            },
        )
        self.assertEqual(
            [card.owner for card in prediction.cards],
            [
                "caster/zhuge_liang",
                "caster/zhuge_liang",
                "caster/merlin",
                "caster/zhuge_liang",
                "caster/merlin",
            ],
        )
        self.assertFalse(prediction.has_low_confidence)
        self.assertFalse(prediction.joint_low_confidence)
        self.assertGreater(prediction.joint_margin, 0.0)
        self.assertGreaterEqual(len(prediction.assignment_candidates), 1)
        self.assertEqual(len(prediction.traces), 5)
        self.assertEqual(prediction.traces[4].owner, "caster/merlin")
        self.assertGreaterEqual(len(prediction.traces[4].scores), 3)
        self.assertFalse(prediction.traces[4].low_confidence)
        self.assertGreaterEqual(prediction.traces[4].scores[0].valid_part_count, 2)
        self.assertGreater(len(prediction.traces[4].scores[0].part_scores), 0)
        self.assertGreater(prediction.traces[4].scores[0].visible_weight_sum, 0.0)
        self.assertIsNotNone(prediction.traces[4].scores[0].part_scores[0].part_name)

    def test_recognize_frontline_matches_left_slot_alignment_sample(self) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)

        screen = load_rgb_image(FAILED_IMAGE_PATH_5)
        prediction = recognizer.analyze_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        self.assertEqual(
            prediction.owners,
            {
                1: "caster/merlin",
                2: "caster/zhuge_liang",
                3: "caster/merlin",
                4: "berserker/morgan",
                5: "caster/merlin",
            },
        )

    def test_recognize_frontline_keeps_slot2_quick_merlin_on_runtime_evidence_samples(
        self,
    ) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)

        expected_by_file = {
            RUNTIME_EVIDENCE_FAILED_SLOT2_QUICK_1: {
                1: "berserker/morgan",
                2: "caster/merlin",
                3: "caster/zhuge_liang",
                4: "caster/merlin",
                5: "berserker/morgan",
            },
            RUNTIME_EVIDENCE_FAILED_SLOT2_QUICK_2: {
                1: "berserker/morgan",
                2: "caster/merlin",
                3: "caster/merlin",
                4: "caster/zhuge_liang",
                5: "caster/merlin",
            },
        }
        for screen_path in expected_by_file:
            with self.subTest(screen=screen_path):
                screen = load_rgb_image(_find_command_card_debug_file(screen_path))
                prediction = recognizer.analyze_frontline(
                    screen,
                    [
                        "caster/zhuge_liang",
                        "caster/merlin",
                        "berserker/morgan",
                    ],
                    support_attacker="berserker/morgan",
                )
                self.assertEqual(prediction.owners, expected_by_file[screen_path])
                slot2 = prediction.traces[1]
                self.assertEqual(slot2.color, "quick")
                self.assertEqual(slot2.owner, "caster/merlin")

    def test_failed3_slot3_uses_explicit_crop_and_mask_layout(self) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)

        screen = load_rgb_image(FAILED_IMAGE_PATH_3)
        prediction = recognizer.analyze_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        trace = prediction.traces[2]
        self.assertEqual(trace.crop_region_abs, (844, 615, 1076, 905))
        self.assertEqual(
            trace.mask_rects_abs,
            [
                (844, 615, 1076, 651),
                (844, 793, 1076, 905),
            ],
        )

    def test_crop_command_card_for_recognition_returns_masked_slot_view(self) -> None:
        screen = load_rgb_image(FAILED_IMAGE_PATH_3)

        masked = crop_command_card_for_recognition(screen, 3)

        self.assertEqual(masked.shape, (290, 232, 3))
        self.assertFalse(np.array_equal(masked, screen[615:905, 844:1076]))

    def test_write_masked_preview_image_outputs_overview(self) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)
        screen = load_rgb_image(FAILED_IMAGE_PATH_4)
        prediction = recognizer.analyze_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "遮挡总览.png"
            write_masked_preview_image(output_path, prediction, screen)

            self.assertTrue(output_path.exists())
            preview = load_rgb_image(output_path)
            self.assertGreater(preview.shape[1], preview.shape[0])

    def test_write_part_preview_image_outputs_patch_overview(self) -> None:
        resources = ResourceCatalog()
        recognizer = CommandCardRecognizer(resources)
        screen = load_rgb_image(FAILED_IMAGE_PATH_4)
        prediction = recognizer.analyze_frontline(
            screen,
            [
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
        )

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "局部总览.png"
            write_part_preview_image(output_path, prediction, screen)

            self.assertTrue(output_path.exists())
            preview = load_rgb_image(output_path)
            self.assertGreater(preview.shape[1], 0)
            self.assertGreater(preview.shape[0], 0)

    def test_prediction_has_low_confidence_includes_joint_result(self) -> None:
        prediction = CommandCardPrediction(
            frontline_servants=[
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
            traces=[
                CommandCardTrace(
                    index=1,
                    owner="caster/zhuge_liang",
                    color="arts",
                    score=0.20,
                    margin=0.01,
                    support_badge=False,
                    low_confidence=False,
                    scores=[CommandCardScore("caster/zhuge_liang", 0.20)],
                )
            ],
            min_score=0.07,
            min_margin=0.002,
            joint_score=0.18,
            joint_margin=0.001,
            joint_low_confidence=True,
            assignment_candidates=[
                CommandCardAssignmentCandidate(
                    owners_by_index={1: "caster/zhuge_liang"},
                    score=0.18,
                    margin_from_best=0.0,
                )
            ],
        )

        self.assertTrue(prediction.has_low_confidence)


if __name__ == "__main__":
    unittest.main()
