import unittest
from pathlib import Path

from core.shared import ResourceCatalog, load_battle_config
from core.support_recognition import SupportPortraitVerifier

REPO_ROOT = Path(__file__).resolve().parents[2]


class SupportVerifierReplayTest(unittest.TestCase):
    def setUp(self) -> None:
        resources = ResourceCatalog()
        config = load_battle_config().support.recognition
        self.verifier = SupportPortraitVerifier.from_servant(
            "berserker/morgan",
            resources,
            config,
        )

    def test_replays_positive_morgan_samples(self) -> None:
        positive_dir = REPO_ROOT / "test_image" / "support" / "morgan"
        for image_path in sorted(positive_dir.glob("*.png")):
            with self.subTest(image=image_path.name):
                result = self.verifier.match_image(image_path)
                self.assertIsNotNone(result)
                assert result is not None
                self.assertEqual(result.slot_index, 2)

    def test_replays_negative_non_morgan_samples(self) -> None:
        negative_dir = REPO_ROOT / "test_image" / "support" / "non_morgan"
        for image_path in sorted(negative_dir.glob("*.png")):
            with self.subTest(image=image_path.name):
                self.assertIsNone(self.verifier.match_image(image_path))


if __name__ == "__main__":
    unittest.main()
