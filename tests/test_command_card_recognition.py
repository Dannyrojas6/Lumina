import unittest
from pathlib import Path

import numpy as np

from core.battle_runtime.command_card_recognition import (
    CommandCardRecognizer,
    collect_command_card_reference_paths,
    crop_command_card_face,
    mask_command_card_info_strip,
)
from core.shared.resource_catalog import ResourceCatalog
from core.shared.screen_coordinates import GameCoordinates

TEST_IMAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "test_image"
    / "fight"
    / "指令卡梅林摩根诸葛亮.png"
)
FAILED_IMAGE_PATH = (
    Path(__file__).resolve().parents[1] / "test_image" / "指令卡识别失败1.png"
)
FAILED_IMAGE_PATH_2 = (
    Path(__file__).resolve().parents[1] / "test_image" / "指令卡识别失败2.png"
)


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


if __name__ == "__main__":
    unittest.main()
