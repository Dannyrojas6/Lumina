import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import yaml
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QFrame, QTextEdit, QVBoxLayout

from core.gui.app.qt_app import ensure_qt_application
from core.gui.tools.coordinate_page import CoordinateCanvas, CoordinateToolPage
from core.gui.tools.custom_sequence_page import CustomSequencePage
from core.gui.tools.mask_region_page import (
    MaskCanvas,
    MaskRegionToolPage,
    qimage_to_rgb_array,
)


class GuiToolTests(unittest.TestCase):
    def setUp(self) -> None:
        ensure_qt_application()

    def test_custom_sequence_page_loads_selected_sequence_and_saves_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            config_dir = base / "config"
            sequence_dir = config_dir / "custom_sequences"
            sequence_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            sequence_path = sequence_dir / "demo.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "battle_mode": "custom_sequence",
                        "custom_sequence_battle": {"sequence": "demo.yaml"},
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            sequence_path.write_text("turns: []\n", encoding="utf-8")

            page = CustomSequencePage(config_path=config_path)
            self.assertEqual(page.current_sequence_name(), "demo.yaml")

            page.set_current_turn(1, 1)
            page.add_enemy_target_action(2)
            page.save_sequence()

            saved = yaml.safe_load(sequence_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["turns"][0]["wave"], 1)
            self.assertEqual(saved["turns"][0]["turn"], 1)
            self.assertEqual(saved["turns"][0]["actions"][0]["type"], "enemy_target")
            self.assertEqual(saved["turns"][0]["actions"][0]["target"], 2)

    def test_coordinate_tool_page_can_be_created(self) -> None:
        page = CoordinateToolPage()
        self.assertEqual(page.window_title(), "坐标工具")
        self.assertIsInstance(page.layout(), QVBoxLayout)
        side_panel = page.findChild(QFrame, "coordinateToolSidePanel")
        self.assertIsNotNone(side_panel)
        self.assertEqual(side_panel.maximumWidth(), 360)

    def test_mask_region_tool_page_can_be_created(self) -> None:
        page = MaskRegionToolPage()
        self.assertEqual(page.window_title(), "遮挡工具")
        self.assertIsInstance(page.layout(), QVBoxLayout)
        side_panel = page.findChild(QFrame, "maskToolSidePanel")
        self.assertIsNotNone(side_panel)
        self.assertEqual(side_panel.width(), 340)
        self.assertEqual(side_panel.minimumWidth(), 340)
        self.assertEqual(side_panel.maximumWidth(), 340)

    def test_custom_sequence_page_removes_large_hint_text_box(self) -> None:
        page = CustomSequencePage()
        self.assertEqual(len(page.findChildren(QTextEdit)), 0)
        side_panel = page.findChild(QFrame, "customSequenceSidePanel")
        self.assertIsNotNone(side_panel)
        self.assertEqual(side_panel.maximumWidth(), 360)

    def test_coordinate_canvas_prefers_live_drag_preview_over_previous_rect(self) -> None:
        canvas = CoordinateCanvas()
        canvas.latest_rect = (10, 10, 30, 30)
        canvas.drag_preview = (40, 40, 80, 80)

        self.assertEqual(canvas.active_rect_to_draw(), (40, 40, 80, 80))

    def test_coordinate_canvas_uses_crosshair_marker(self) -> None:
        canvas = CoordinateCanvas()

        horizontal, vertical = canvas.crosshair_segments((100, 120))

        self.assertEqual(horizontal[0], (92.0, 120.0))
        self.assertEqual(horizontal[1], (108.0, 120.0))
        self.assertEqual(vertical[0], (100.0, 112.0))
        self.assertEqual(vertical[1], (100.0, 128.0))

    def test_mask_canvas_zoom_keeps_cursor_anchor(self) -> None:
        canvas = MaskCanvas()
        canvas.resize(800, 600)
        image = QImage(400, 200, QImage.Format.Format_RGB32)
        image.fill(QColor("#445566"))
        canvas.set_qimage(image)
        focus = QPointF(200, 150)

        before = canvas.widget_to_image_float(focus)
        canvas.zoom_at(focus, 1.5)
        after = canvas.widget_to_image_float(focus)

        self.assertAlmostEqual(before.x(), after.x(), delta=0.5)
        self.assertAlmostEqual(before.y(), after.y(), delta=0.5)

    def test_mask_canvas_clear_actions_reset_drag_state(self) -> None:
        canvas = MaskCanvas()
        canvas.drag_origin = (10, 10)
        canvas.drag_preview = (10, 10, 20, 20)
        canvas.drag_mode = "mask"
        canvas.mask_rects = [(10, 10, 20, 20)]
        canvas.crop_rect = (0, 0, 30, 30)

        canvas.clear_masks()

        self.assertEqual(canvas.mask_rects, [])
        self.assertIsNone(canvas.drag_origin)
        self.assertIsNone(canvas.drag_preview)
        self.assertIsNone(canvas.drag_mode)

        canvas.drag_origin = (10, 10)
        canvas.drag_preview = (10, 10, 20, 20)
        canvas.drag_mode = "crop"
        canvas.mask_rects = [(10, 10, 20, 20)]
        canvas.crop_rect = (0, 0, 30, 30)

        canvas.clear_all()

        self.assertIsNone(canvas.crop_rect)
        self.assertEqual(canvas.mask_rects, [])
        self.assertIsNone(canvas.drag_origin)
        self.assertIsNone(canvas.drag_preview)
        self.assertIsNone(canvas.drag_mode)

    def test_mask_region_previews_are_centered(self) -> None:
        page = MaskRegionToolPage()

        self.assertEqual(
            page.crop_preview.alignment(),
            Qt.AlignmentFlag.AlignCenter,
        )
        self.assertEqual(
            page.mask_preview.alignment(),
            Qt.AlignmentFlag.AlignCenter,
        )
        self.assertEqual(page.crop_preview.minimumHeight(), 180)
        self.assertEqual(page.crop_preview.maximumHeight(), 180)
        self.assertEqual(page.mask_preview.minimumHeight(), 180)
        self.assertEqual(page.mask_preview.maximumHeight(), 180)
        self.assertEqual(page.export_edit.minimumHeight(), 220)
        self.assertEqual(page.export_edit.maximumHeight(), 220)

    def test_mask_canvas_export_clips_masks_to_crop_region(self) -> None:
        canvas = MaskCanvas()
        image = QImage(400, 300, QImage.Format.Format_RGB32)
        image.fill(QColor("#445566"))
        canvas.set_qimage(image)
        canvas.image_path = Path("sample.png")
        canvas.crop_rect = (100, 100, 200, 200)
        canvas.mask_rects = [
            (50, 150, 250, 220),
            (120, 120, 160, 160),
        ]

        export_text = canvas.export_text()

        self.assertIn("MASK_RECTS = [", export_text)
        self.assertIn("(0, 50, 100, 100)", export_text)
        self.assertIn("(20, 20, 60, 60)", export_text)
        self.assertNotIn("(-", export_text)

    def test_qimage_to_rgb_array_handles_row_padding(self) -> None:
        image = QImage(331, 54, QImage.Format.Format_RGB32)
        image.fill(QColor("#123456"))

        rgb = qimage_to_rgb_array(image)

        self.assertEqual(rgb.shape, (54, 331, 3))
        self.assertEqual(tuple(rgb[0, 0]), (18, 52, 86))
