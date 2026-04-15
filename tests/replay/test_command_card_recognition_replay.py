import unittest

from core.command_card_recognition import CommandCardRecognizer, load_command_card_samples
from core.support_recognition import load_rgb_image
from core.shared import ResourceCatalog


class CommandCardReplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.recognizer = CommandCardRecognizer(ResourceCatalog())
        self.samples = load_command_card_samples()

    def test_replays_all_samples_from_truth_catalog(self) -> None:
        for sample in self.samples:
            with self.subTest(sample=sample.image):
                screen = load_rgb_image(sample.image_path)
                prediction = self.recognizer.analyze_frontline(
                    screen,
                    sample.frontline,
                    support_attacker=sample.support_attacker,
                )
                self.assertEqual(prediction.owners, sample.owners_by_index)
                self.assertEqual(
                    [card.owner for card in prediction.cards],
                    list(sample.owners_by_index.values()),
                )
                self.assertFalse(
                    prediction.has_low_confidence,
                    f"{sample.image} should not be low confidence in replay baseline",
                )


if __name__ == "__main__":
    unittest.main()
