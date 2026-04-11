import unittest
from pathlib import Path

from core.battle_runtime.command_card_recognition import (
    CommandCardInfo,
    detect_command_card_color,
    choose_best_card_chain,
)
from core.shared.screen_coordinates import GameCoordinates
from core.support_recognition import load_rgb_image
from core.runtime.workflow import build_command_card_plan
import numpy as np

TEST_IMAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "test_image"
    / "fight"
    / "指令卡梅林摩根诸葛亮.png"
)


def make_color_block(color: str) -> np.ndarray:
    rgb_map = {
        "buster": np.array([220, 72, 52], dtype=np.uint8),
        "arts": np.array([64, 120, 232], dtype=np.uint8),
        "quick": np.array([72, 210, 120], dtype=np.uint8),
    }
    image = np.zeros((341, 270, 3), dtype=np.uint8)
    image[:, :] = rgb_map[color]
    return image


class CommandCardChainTest(unittest.TestCase):
    def test_card_positions_match_command_card_region_centers(self) -> None:
        expected = {
            index: GameCoordinates.region_center(region)
            for index, region in GameCoordinates.COMMAND_CARD_REGIONS.items()
        }

        self.assertEqual(GameCoordinates.CARD_POSITIONS, expected)

    def test_support_attacker_same_servant_beats_buster_chain(self) -> None:
        cards = [
            CommandCardInfo(index=1, owner="caster/merlin", color="buster"),
            CommandCardInfo(index=2, owner="caster/merlin", color="arts"),
            CommandCardInfo(index=3, owner="caster/merlin", color="quick"),
            CommandCardInfo(index=4, owner="berserker/morgan", color="buster"),
            CommandCardInfo(index=5, owner="berserker/morgan", color="buster"),
        ]

        best = choose_best_card_chain(
            cards=cards,
            servant_priority=["caster/merlin", "berserker/morgan"],
            support_attacker="caster/merlin",
        )

        self.assertEqual([item.index for item in best], [1, 2, 3])

    def test_detect_command_card_color_recognizes_primary_rgb_groups(self) -> None:
        self.assertEqual(detect_command_card_color(make_color_block("buster")), "buster")
        self.assertEqual(detect_command_card_color(make_color_block("arts")), "arts")
        self.assertEqual(detect_command_card_color(make_color_block("quick")), "quick")

    def test_detect_command_card_color_matches_merlin_morgan_zhuge_sample(self) -> None:
        screen = load_rgb_image(TEST_IMAGE_PATH)
        colors = {}
        for card_index, region in GameCoordinates.COMMAND_CARD_REGIONS.items():
            x1, y1, x2, y2 = region
            card_rgb = screen[y1:y2, x1:x2].copy()
            colors[card_index] = detect_command_card_color(card_rgb)

        self.assertEqual(
            colors,
            {
                1: "buster",
                2: "quick",
                3: "quick",
                4: "buster",
                5: "arts",
            },
        )

    def test_build_command_card_plan_uses_chain_priority_before_servant_fallback(self) -> None:
        cards = [
            CommandCardInfo(index=1, owner="caster/merlin", color="buster"),
            CommandCardInfo(index=2, owner="caster/merlin", color="arts"),
            CommandCardInfo(index=3, owner="caster/merlin", color="quick"),
            CommandCardInfo(index=4, owner="berserker/morgan", color="buster"),
            CommandCardInfo(index=5, owner="berserker/morgan", color="buster"),
        ]

        plan = build_command_card_plan(
            noble_indices=[],
            card_owners={card.index: card.owner for card in cards},
            servant_priority=["berserker/morgan", "caster/merlin"],
            cards=cards,
            support_attacker="caster/merlin",
        )

        self.assertEqual(
            plan,
            [
                {"type": "card", "index": 1},
                {"type": "card", "index": 2},
                {"type": "card", "index": 3},
            ],
        )


if __name__ == "__main__":
    unittest.main()
