import unittest
from pathlib import Path

import cv2
import numpy as np

from core.perception import ImageRecognizer, StateDetector
from core.shared import GameState, ResourceCatalog

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_gray_image(path: Path) -> np.ndarray:
    raw_bytes = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(raw_bytes, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


class StateDetectionReplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.resources = ResourceCatalog()
        self.recognizer = ImageRecognizer(threshold=0.7)

    def _detect_state(self, image_path: Path) -> GameState:
        detector = StateDetector(
            recognizer=self.recognizer,
            screen_callback=lambda: str(image_path),
            resources=self.resources,
            screen_array_callback=lambda: _load_gray_image(image_path),
        )
        return detector.detect().state

    def test_detects_main_runtime_states_from_replay_images(self) -> None:
        cases = [
            (
                REPO_ROOT / "test_image" / "main_menu" / "主菜单.png",
                GameState.MAIN_MENU,
            ),
            (
                REPO_ROOT
                / "test_image"
                / "support"
                / "morgan"
                / "助战选择界面摩根1.png",
                GameState.SUPPORT_SELECT,
            ),
            (
                REPO_ROOT / "test_image" / "fight" / "指令卡选择界面.png",
                GameState.CARD_SELECT,
            ),
        ]
        for image_path, expected_state in cases:
            with self.subTest(image=str(image_path)):
                self.assertEqual(self._detect_state(image_path), expected_state)

    def test_detects_three_battle_result_stages_from_replay_images(self) -> None:
        cases = [
            REPO_ROOT / "test_image" / "fight_result" / "战斗结果1.png",
            REPO_ROOT / "test_image" / "fight_result" / "战斗结果2.png",
            REPO_ROOT / "test_image" / "fight_result" / "战斗结果3.png",
        ]
        for image_path in cases:
            with self.subTest(image=image_path.name):
                self.assertEqual(
                    self._detect_state(image_path),
                    GameState.BATTLE_RESULT,
                )


if __name__ == "__main__":
    unittest.main()
