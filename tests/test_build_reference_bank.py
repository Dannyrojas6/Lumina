import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from core.shared.resource_manifest import SupportRecognitionManifest
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

    def test_reference_meta_to_json_canonicalizes_model_path(self) -> None:
        meta = PortraitReferenceMeta(
            servant_name="berserker/morgan",
            model_path="models/portrait_encoder.onnx",
            image_size=24,
            embedding_dim=128,
        )

        with TemporaryDirectory() as tmp_dir:
            meta_path = Path(tmp_dir) / "reference_meta.json"
            meta.to_json(meta_path)
            payload = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["model_path"], "assets/models/portrait_encoder.onnx")

    def test_reference_meta_from_json_rejects_legacy_model_path(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            meta_path = Path(tmp_dir) / "reference_meta.json"
            meta_path.write_text(
                json.dumps(
                    {
                        "servant_name": "berserker/morgan",
                        "model_path": "models/portrait_encoder.onnx",
                        "image_size": 24,
                        "embedding_dim": 128,
                        "portrait_crop": [24, 18, 176, 170],
                        "face_crop": [30, 18, 150, 128],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "model_path"):
                PortraitReferenceMeta.from_json(meta_path)

    def test_build_reference_bank_rejects_source_glob_escape(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_glob"):
            SupportRecognitionManifest(
                source_dir="atlas/faces",
                source_glob="../../../escape.png",
                generated_dir="support/generated",
                reference_bank="support/generated/reference_bank.npz",
                reference_meta="support/generated/reference_meta.json",
            )


if __name__ == "__main__":
    unittest.main()
