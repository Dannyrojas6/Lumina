import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import yaml
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

from core.gui.app.main_window import LuminaMainWindow, compute_initial_window_geometry
from core.gui.app.qt_app import ensure_qt_application
from core.gui.runtime.controller import RuntimeController
from core.gui.runtime.runtime_page import RuntimePage
from core.gui.services.runtime_config_service import RuntimeEditableConfig


class DummyRuntimeController(RuntimeController):
    def __init__(self) -> None:
        super().__init__()
        self.started = 0
        self.stopped = 0
        self.current_summary = "\n".join(
            [
                "battle_mode=main",
                "smart_battle=off",
                "continue_battle=True",
                "log_level=INFO",
                "support=berserker/morgan",
                "custom_sequence=demo.yaml",
            ]
        )
        self.editable_config = RuntimeEditableConfig(
            battle_mode="main",
            smart_battle_enabled=False,
            continue_battle=True,
            log_level="INFO",
        )
        self.applied_configs: list[RuntimeEditableConfig] = []

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def load_editable_config(self) -> RuntimeEditableConfig:
        return self.editable_config

    def apply_editable_config(self, config: RuntimeEditableConfig) -> None:
        self.editable_config = config
        self.applied_configs.append(config)
        self.current_summary = "\n".join(
            [
                f"battle_mode={config.battle_mode}",
                f"smart_battle={'on' if config.smart_battle_enabled else 'off'}",
                f"continue_battle={config.continue_battle}",
                f"log_level={config.log_level}",
                "support=berserker/morgan",
                "custom_sequence=demo.yaml",
            ]
        )
        self.summary_changed.emit(self.current_summary)


class GuiAppTests(unittest.TestCase):
    def setUp(self) -> None:
        ensure_qt_application()

    def test_ensure_qt_application_returns_application(self) -> None:
        app = ensure_qt_application()
        self.assertIsInstance(app, QApplication)

    def test_main_window_contains_all_primary_workspaces(self) -> None:
        controller = DummyRuntimeController()
        window = LuminaMainWindow(runtime_controller=controller)
        screen = QApplication.primaryScreen()
        assert screen is not None
        available = screen.availableGeometry()
        dpr_scale = float(screen.devicePixelRatio() or 1.0)
        dpi_scale = float(screen.logicalDotsPerInch() or 96.0) / 96.0
        expected_geometry = compute_initial_window_geometry(
            available_x=available.x(),
            available_y=available.y(),
            available_width=available.width(),
            available_height=available.height(),
            scale_factor=max(dpr_scale, dpi_scale, 1.0),
        )

        self.assertEqual(
            window.workspace_names(),
            ["运行", "自定义操作序列", "坐标工具", "遮挡工具"],
        )
        self.assertTrue(hasattr(window, "workspace_tabs"))
        self.assertFalse(hasattr(window, "nav_list"))
        self.assertFalse(hasattr(window, "page_hint_label"))
        self.assertFalse(hasattr(window, "log_frame"))
        self.assertTrue(hasattr(window.runtime_page, "log_toggle_button"))
        self.assertEqual(window.x(), expected_geometry[0])
        self.assertEqual(window.y(), expected_geometry[1])
        self.assertEqual(window.width(), expected_geometry[2])
        self.assertEqual(window.height(), expected_geometry[3])

    def test_compute_initial_window_geometry_converts_physical_target_to_logical_size(self) -> None:
        x, y, width, height = compute_initial_window_geometry(
            available_x=0,
            available_y=0,
            available_width=1707,
            available_height=960,
            scale_factor=1.5,
        )

        self.assertEqual(width, 1280)
        self.assertEqual(height, 720)
        self.assertEqual(x, 213)
        self.assertEqual(y, 120)

    def test_runtime_page_start_stop_buttons_call_controller(self) -> None:
        controller = DummyRuntimeController()
        window = LuminaMainWindow(runtime_controller=controller)

        window.runtime_page.start_button.click()
        controller.lifecycle_changed.emit("运行中")
        controller.running_changed.emit(True)
        window.runtime_page.stop_button.click()

        self.assertEqual(controller.started, 1)
        self.assertEqual(controller.stopped, 1)

    def test_runtime_page_start_does_not_fake_running_before_worker_reports_running(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.start_button.click()

        self.assertEqual(controller.started, 1)
        self.assertEqual(page.status_value.text(), "启动中")
        self.assertFalse(page.start_button.isEnabled())
        self.assertFalse(page.stop_button.isEnabled())

    def test_runtime_page_failure_recovers_idle_controls_without_clearing_failure_text(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.start_button.click()
        controller.lifecycle_changed.emit("运行失败：no ready adb device found")
        controller.running_changed.emit(False)

        self.assertTrue(page.start_button.isEnabled())
        self.assertFalse(page.stop_button.isEnabled())
        self.assertEqual(page.status_value.text(), "运行失败：no ready adb device found")

    def test_runtime_page_log_drawer_starts_collapsed(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        self.assertFalse(page.log_output.isVisible())
        self.assertEqual(page.log_toggle_button.text(), "展开")

    def test_runtime_page_loads_editable_config_controls(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        self.assertEqual(page.mode_combo.currentText(), "main")
        self.assertFalse(page.smart_battle_checkbox.isChecked())
        self.assertTrue(page.continue_battle_checkbox.isChecked())
        self.assertEqual(page.log_level_combo.currentText(), "INFO")
        self.assertEqual(page.config_status_label.text(), "已保存配置")

    def test_runtime_page_marks_dirty_and_applies_runtime_config(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.log_level_combo.setCurrentText("DEBUG")

        self.assertEqual(page.config_status_label.text(), "有未应用修改")
        self.assertTrue(page.apply_button.isEnabled())
        page.apply_button.click()

        self.assertEqual(len(controller.applied_configs), 1)
        self.assertEqual(controller.applied_configs[0].log_level, "DEBUG")
        self.assertEqual(page.config_status_label.text(), "已保存配置")
        self.assertEqual(page.log_level_value.text(), "DEBUG")

    def test_runtime_page_restore_discards_unsaved_changes(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.mode_combo.setCurrentText("custom_sequence")
        self.assertEqual(page.config_status_label.text(), "有未应用修改")

        page.reset_button.click()

        self.assertEqual(page.mode_combo.currentText(), "main")
        self.assertEqual(page.config_status_label.text(), "已保存配置")

    def test_runtime_page_custom_sequence_disables_smart_battle_checkbox(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.mode_combo.setCurrentText("custom_sequence")

        self.assertFalse(page.smart_battle_checkbox.isEnabled())

    def test_runtime_page_uses_neutral_checkbox_style_for_runtime_toggles(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        smart_style = page.smart_battle_checkbox.styleSheet()
        continue_style = page.continue_battle_checkbox.styleSheet()

        self.assertEqual(smart_style, continue_style)
        self.assertIn("QCheckBox::indicator:checked", smart_style)
        self.assertIn("image: none", smart_style)
        self.assertIn("width: 16px", smart_style)
        self.assertIn("#8b5cf6", smart_style)
        self.assertEqual(page.smart_battle_checkbox.text(), "")
        self.assertEqual(page.continue_battle_checkbox.text(), "")

    def test_runtime_page_running_state_disables_config_controls(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        controller.lifecycle_changed.emit("运行中")
        controller.running_changed.emit(True)

        self.assertFalse(page.mode_combo.isEnabled())
        self.assertFalse(page.apply_button.isEnabled())
        self.assertFalse(page.reset_button.isEnabled())

    def test_runtime_page_preview_update_keeps_layout_hints_stable(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        before_page_hint = page.sizeHint()
        before_preview_hint = page.preview_label.sizeHint()

        image = QImage(1920, 1080, QImage.Format.Format_RGB888)
        page.set_preview_image(image)

        self.assertEqual(page.left_card.minimumWidth(), 340)
        self.assertEqual(page.left_card.maximumWidth(), 340)
        self.assertEqual(page.sizeHint(), before_page_hint)
        self.assertEqual(page.preview_label.sizeHint(), before_preview_hint)


class RuntimeConfigServiceTests(unittest.TestCase):
    def test_save_runtime_editable_config_updates_only_targeted_fields(self) -> None:
        from core.gui.services.runtime_config_service import (
            load_runtime_editable_config,
            save_runtime_editable_config,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "battle_config.yaml"
            original = (
                "loop_count: 10\n"
                "battle_mode: custom_sequence # mode comment\n"
                "continue_battle: true # continue comment\n"
                "log_level: DEBUG # log comment\n"
                "support:\n"
                "  class: berserker\n"
                "smart_battle:\n"
                "  enabled: true # smart comment\n"
                "  frontline: []\n"
            )
            config_path.write_text(original, encoding="utf-8")

            loaded = load_runtime_editable_config(config_path)
            self.assertEqual(loaded.battle_mode, "custom_sequence")
            self.assertTrue(loaded.smart_battle_enabled)
            self.assertTrue(loaded.continue_battle)
            self.assertEqual(loaded.log_level, "DEBUG")

            save_runtime_editable_config(
                config_path,
                RuntimeEditableConfig(
                    battle_mode="main",
                    smart_battle_enabled=False,
                    continue_battle=False,
                    log_level="INFO",
                ),
            )

            updated_text = config_path.read_text(encoding="utf-8")
            self.assertIn("battle_mode: main # mode comment", updated_text)
            self.assertIn("continue_battle: false # continue comment", updated_text)
            self.assertIn("log_level: INFO # log comment", updated_text)
            self.assertIn("  enabled: false # smart comment", updated_text)
            self.assertIn("  class: berserker", updated_text)
