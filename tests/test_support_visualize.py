import unittest

import numpy as np

from core.shared.screen_coordinates import GameCoordinates
from core.support_recognition.verifier import (
    SupportPortraitSlotScore,
    SupportPortraitVerification,
)
from core.support_recognition.visualize import annotate_support_screen


class SupportVisualizeTest(unittest.TestCase):
    def test_annotate_support_screen_uses_fixed_slot_regions(self) -> None:
        screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
        canonical_region = GameCoordinates.SUPPORT_PORTRAIT_SLOT_REGIONS[1]
        shifted_region = (
            canonical_region[0],
            canonical_region[1] - 200,
            canonical_region[2],
            canonical_region[3] - 200,
        )
        best_slot = SupportPortraitSlotScore(
            slot_index=1,
            score=0.123,
            region=shifted_region,
            click_position=(0, 0),
            positive_score=0.0,
            negative_score=0.0,
            masked_full_positive=0.0,
            masked_face_positive=0.0,
            masked_full_negative=0.0,
            masked_face_negative=0.0,
        )
        analysis = SupportPortraitVerification(
            servant_name="berserker/morgan",
            slot_scores=[best_slot],
            best_slot=best_slot,
            second_slot=None,
            margin=0.0,
            min_score=0.78,
            min_margin=0.004,
        )

        annotated = annotate_support_screen(screen, analysis)

        canonical_x1, canonical_y1, *_ = canonical_region
        shifted_x1, shifted_y1, *_ = shifted_region

        self.assertTupleEqual(
            tuple(int(value) for value in annotated[canonical_y1, canonical_x1]),
            (0, 255, 0),
        )
        self.assertTupleEqual(
            tuple(int(value) for value in annotated[shifted_y1, shifted_x1]),
            (0, 0, 0),
        )


if __name__ == "__main__":
    unittest.main()
