import unittest

import numpy as np

from scripts.mask_region_picker import (
    CropRect,
    MaskRect,
    apply_masks,
    build_default_export,
    crop_image,
    format_export_block,
)


class MaskRegionPickerLogicTest(unittest.TestCase):
    def test_crop_image_uses_selected_region(self) -> None:
        image = np.arange(6 * 8 * 3, dtype=np.uint8).reshape(6, 8, 3)

        cropped = crop_image(image, CropRect(1, 2, 5, 6))

        self.assertEqual(cropped.shape, (4, 4, 3))
        self.assertTrue(np.array_equal(cropped, image[2:6, 1:5]))

    def test_apply_masks_neutralizes_each_mask_rect(self) -> None:
        image = np.zeros((6, 8, 3), dtype=np.uint8)
        image[:, :] = [10, 20, 30]
        image[1:3, 2:6] = [250, 10, 10]

        masked = apply_masks(image, [MaskRect(2, 1, 6, 3)])

        self.assertEqual(masked.shape, image.shape)
        self.assertFalse(np.all(masked[1:3, 2:6] == [250, 10, 10]))

    def test_format_export_block_outputs_python_ready_text(self) -> None:
        export = format_export_block(
            image_name="sample.png",
            crop_rect=CropRect(10, 20, 110, 220),
            masks=[MaskRect(0, 0, 100, 20), MaskRect(60, 30, 90, 70)],
        )

        self.assertIn("sample.png", export)
        self.assertIn("CROP_REGION = (10, 20, 110, 220)", export)
        self.assertIn("MASK_RECTS = [", export)
        self.assertIn("(60, 30, 90, 70)", export)

    def test_build_default_export_contains_comment_and_masks(self) -> None:
        text = build_default_export(
            "sample.png",
            (10, 20, 110, 220),
            [(0, 0, 100, 20)],
        )

        self.assertIn("sample.png", text)
        self.assertIn("MASK_RECTS", text)


if __name__ == "__main__":
    unittest.main()
