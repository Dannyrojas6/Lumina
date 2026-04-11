import unittest

from core.support_recognition.bank import PortraitReferenceMeta
from scripts.build_reference_bank import _calibrate_meta


class _UnusedVerifier:
    pass


class BuildReferenceBankCalibrationTest(unittest.TestCase):
    def test_atlas_only_bank_uses_relaxed_score_floor(self) -> None:
        base_meta = PortraitReferenceMeta(
            servant_name="berserker/morgan",
            model_path="models/portrait_encoder.onnx",
            image_size=24,
            embedding_dim=128,
        )

        calibrated = _calibrate_meta(
            base_meta=base_meta,
            verifier=_UnusedVerifier(),
            positive_images=[],
            negative_images=[],
            expected_slot=2,
        )

        self.assertAlmostEqual(calibrated.min_score, 0.27, places=6)
        self.assertAlmostEqual(calibrated.min_margin, 0.15, places=6)


if __name__ == "__main__":
    unittest.main()
