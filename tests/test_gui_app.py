import os
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import yaml
from PIL import Image
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel, QListView, QPushButton, QSplitter, QTabBar
from PySide6.QtGui import QImage

from core.gui.app.main_window import LuminaMainWindow, compute_initial_window_geometry
from core.gui.app.style import build_app_stylesheet
from core.gui.app.qt_app import ensure_qt_application
from core.gui.runtime.controller import (
    AutomationRuntimeController,
    AutomationRuntimeWorker,
    RuntimeController,
)
from core.gui.runtime.runtime_page import RuntimePage, _RuntimeToggleSwitch
from core.gui.services.runtime_config_service import RuntimeEditableConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ICON_PNG_PATH = REPO_ROOT / "assets" / "ui" / "app_icon.png"
APP_ICON_ICO_PATH = REPO_ROOT / "assets" / "ui" / "app_icon.ico"


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


class FakeManagedWorker(QObject):
    log_emitted = Signal(str)
    state_changed = Signal(str)
    preview_changed = Signal(QImage)
    run_started = Signal()
    run_completed = Signal()
    run_failed = Signal(str)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.start_calls = 0
        self.stop_calls = 0
        self._running = False

    def start(self) -> None:
        self.start_calls += 1
        self._running = True

    def isRunning(self) -> bool:
        return self._running

    def request_stop(self) -> None:
        self.stop_calls += 1

    def finish(self) -> None:
        self._running = False
        self.finished.emit()


class FakeRuntimeProcess:
    def __init__(self) -> None:
        self.terminate_calls = 0
        self.kill_calls = 0
        self._alive = True

    def is_alive(self) -> bool:
        return self._alive

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1


class GuiAppTests(unittest.TestCase):
    def setUp(self) -> None:
        ensure_qt_application()

    def test_ensure_qt_application_returns_application(self) -> None:
        app = ensure_qt_application()
        self.assertIsInstance(app, QApplication)
        self.assertFalse(app.windowIcon().isNull())

    def test_gui_icon_assets_exist_and_use_transparent_corners(self) -> None:
        self.assertTrue(APP_ICON_PNG_PATH.is_file())
        self.assertTrue(APP_ICON_ICO_PATH.is_file())

        image = QImage(str(APP_ICON_PNG_PATH))
        self.assertFalse(image.isNull())
        self.assertEqual(image.width(), image.height())
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        self.assertEqual(image.pixelColor(image.width() - 1, 0).alpha(), 0)
        self.assertEqual(image.pixelColor(0, image.height() - 1).alpha(), 0)
        self.assertEqual(
            image.pixelColor(image.width() - 1, image.height() - 1).alpha(),
            0,
        )
        self.assertGreater(image.pixelColor(image.width() // 2, 60).alpha(), 0)

        with Image.open(APP_ICON_ICO_PATH) as ico:
            self.assertGreaterEqual(
                set(ico.ico.sizes()),
                {(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)},
            )

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
        self.assertTrue(hasattr(window, "header_layout"))
        self.assertFalse(hasattr(window, "nav_list"))
        self.assertFalse(hasattr(window, "page_hint_label"))
        self.assertFalse(hasattr(window, "log_frame"))
        self.assertEqual(window.workspace_tabs.objectName(), "topNavTabs")
        self.assertEqual(window.header_layout.spacing(), 8)
        self.assertEqual(window.header_layout.contentsMargins().left(), 18)
        self.assertEqual(window.header_layout.contentsMargins().right(), 18)
        self.assertEqual(window.header_layout.contentsMargins().top(), 2)
        self.assertEqual(window.header_layout.contentsMargins().bottom(), 2)
        title = window.findChild(QLabel, "mainWindowTitle")
        self.assertIsNotNone(title)
        self.assertEqual(title.text(), "Lumina")
        self.assertEqual(window.x(), expected_geometry[0])
        self.assertEqual(window.y(), expected_geometry[1])
        self.assertEqual(window.width(), expected_geometry[2])
        self.assertEqual(window.height(), expected_geometry[3])
        self.assertFalse(window.windowIcon().isNull())

    def test_app_stylesheet_uses_transparent_label_backgrounds(self) -> None:
        stylesheet = build_app_stylesheet()

        self.assertIn("QLabel {\n        background: transparent;", stylesheet)
        self.assertIn('QLabel[textRole="badge"] {', stylesheet)
        self.assertIn("background: #222222;", stylesheet)

    def test_app_stylesheet_uses_underline_top_nav_style(self) -> None:
        stylesheet = build_app_stylesheet()

        self.assertIn("QTabBar#topNavTabs {", stylesheet)
        self.assertIn("background: transparent;", stylesheet)
        self.assertIn("QTabBar#topNavTabs::tab:selected", stylesheet)
        self.assertIn("border-bottom: 2px solid #26c281;", stylesheet)
        self.assertNotIn("background: #2a2a2a;", stylesheet)
        self.assertIn("padding: 4px 14px 4px 14px;", stylesheet)
        self.assertIn("margin-right: 4px;", stylesheet)
        self.assertIn("min-height: 20px;", stylesheet)

    def test_app_stylesheet_defines_shared_gui_component_roles(self) -> None:
        stylesheet = build_app_stylesheet()
        preview_status_block = stylesheet.split('QLabel#runtimePreviewStatusValue {', 1)[1].split("}", 1)[0]
        side_panel_block = stylesheet.split('QFrame[layoutRole="sidePanel"] {', 1)[1].split("}", 1)[0]
        canvas_panel_block = stylesheet.split('QFrame[layoutRole="canvasPanel"] {', 1)[1].split("}", 1)[0]

        self.assertIn('QComboBox[controlRole="formCombo"] {', stylesheet)
        self.assertIn("padding: 2px 10px;", stylesheet)
        self.assertIn("min-height: 22px;", stylesheet)
        self.assertIn('QListView[viewRole="comboPopup"] {', stylesheet)
        self.assertIn('QPushButton[buttonRole="pillToggle"] {', stylesheet)
        self.assertIn('QFrame[separatorRole="divider"] {', stylesheet)
        self.assertIn('QWidget[headerRole="panel"] {', stylesheet)
        self.assertIn('QLabel[noticeRole="saved"] {', stylesheet)
        self.assertIn('QLabel[noticeRole="dirty"] {', stylesheet)
        self.assertIn('QLabel#runtimeStatusDot[statusState="idle"] {', stylesheet)
        self.assertIn('QLabel#runtimeStatusValue[statusState="idle"] {', stylesheet)
        self.assertIn('QLabel#runtimePreviewStatusValue {', stylesheet)
        self.assertIn("font-size: 11px;", preview_status_block)
        self.assertIn("font-weight: 500;", preview_status_block)
        self.assertIn('QFrame[layoutRole="toolbar"] {', stylesheet)
        self.assertIn('QFrame[layoutRole="sidePanel"] {', stylesheet)
        self.assertIn('QFrame[layoutRole="canvasPanel"] {', stylesheet)
        self.assertIn('QFrame[layoutRole="editorPanel"] {', stylesheet)
        self.assertIn('QTextEdit[editorRole="export"] {', stylesheet)
        self.assertIn('QLabel[textRole="panelTitle"] {', stylesheet)
        self.assertIn('QLabel[textRole="section"] {', stylesheet)
        self.assertIn("font-size: 11px;", stylesheet)
        self.assertIn("background: transparent;", side_panel_block)
        self.assertIn("border: 0;", side_panel_block)
        self.assertNotEqual(side_panel_block.strip(), canvas_panel_block.strip())

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
        self.assertEqual(page.preview_status_value.text(), "启动中")
        self.assertFalse(page.start_button.isEnabled())
        self.assertFalse(page.stop_button.isEnabled())

    def test_runtime_page_failure_recovers_idle_controls_without_clearing_failure_text(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.start_button.click()
        controller.lifecycle_changed.emit("故障")
        controller.running_changed.emit(False)

        self.assertTrue(page.start_button.isEnabled())
        self.assertFalse(page.stop_button.isEnabled())
        self.assertEqual(page.preview_status_value.text(), "故障")

    def test_runtime_page_log_panel_is_always_visible(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        self.assertFalse(page.log_output.isHidden())
        self.assertFalse(hasattr(page, "log_toggle_button"))
        self.assertIsInstance(page.log_clear_button, QPushButton)
        self.assertIsInstance(page.log_popout_button, QPushButton)

    def test_runtime_page_loads_editable_config_controls(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        self.assertEqual(page.mode_combo.currentText(), "main")
        self.assertFalse(page.smart_battle_checkbox.isChecked())
        self.assertTrue(page.continue_battle_checkbox.isChecked())
        self.assertEqual(page.log_level_combo.currentText(), "INFO")
        self.assertEqual(page.config_status_label.text(), "✓ 已保存配置")
        self.assertEqual(page.mode_combo.property("controlRole"), "formCombo")
        self.assertEqual(page.log_level_combo.property("controlRole"), "formCombo")
        self.assertEqual(page.mode_combo.view().property("viewRole"), "comboPopup")
        self.assertEqual(page.log_level_combo.view().property("viewRole"), "comboPopup")
        self.assertEqual(page.mode_combo.minimumWidth(), 138)
        self.assertEqual(page.mode_combo.maximumWidth(), 138)
        self.assertEqual(page.log_level_combo.minimumWidth(), 138)
        self.assertEqual(page.log_level_combo.maximumWidth(), 138)
        self.assertEqual(page.mode_combo.minimumHeight(), 28)
        self.assertEqual(page.mode_combo.maximumHeight(), 28)
        self.assertEqual(page.log_level_combo.minimumHeight(), 28)
        self.assertEqual(page.log_level_combo.maximumHeight(), 28)

    def test_runtime_page_uses_custom_dark_combo_popup_views(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        self.assertIsInstance(page.mode_combo.view(), QListView)
        self.assertIsInstance(page.log_level_combo.view(), QListView)
        self.assertEqual(page.mode_combo.property("controlRole"), "formCombo")
        self.assertEqual(page.log_level_combo.property("controlRole"), "formCombo")
        self.assertEqual(page.mode_combo.styleSheet(), "")
        self.assertEqual(page.log_level_combo.styleSheet(), "")
        self.assertFalse(page.mode_combo.view().wordWrap())
        self.assertFalse(page.log_level_combo.view().wordWrap())
        self.assertEqual(page.mode_combo.view().spacing(), 0)
        self.assertEqual(page.log_level_combo.view().spacing(), 0)
        self.assertTrue(page.mode_combo.view().uniformItemSizes())
        self.assertTrue(page.log_level_combo.view().uniformItemSizes())
        self.assertEqual(page.mode_combo.view().textElideMode(), Qt.TextElideMode.ElideNone)
        self.assertEqual(page.log_level_combo.view().textElideMode(), Qt.TextElideMode.ElideNone)
        self.assertEqual(page.mode_combo.view().property("viewRole"), "comboPopup")
        self.assertEqual(page.log_level_combo.view().property("viewRole"), "comboPopup")
        self.assertEqual(page.mode_combo.view().styleSheet(), "")
        self.assertEqual(page.log_level_combo.view().styleSheet(), "")

    def test_runtime_page_marks_dirty_and_applies_runtime_config(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.log_level_combo.setCurrentText("DEBUG")

        self.assertEqual(page.config_status_label.text(), "有未应用修改")
        self.assertTrue(page.apply_button.isEnabled())
        page.apply_button.click()

        self.assertEqual(len(controller.applied_configs), 1)
        self.assertEqual(controller.applied_configs[0].log_level, "DEBUG")
        self.assertEqual(page.config_status_label.text(), "✓ 已保存配置")
        self.assertEqual(page.log_level_value.text(), "DEBUG")

    def test_runtime_page_restore_discards_unsaved_changes(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.mode_combo.setCurrentText("custom_sequence")
        self.assertEqual(page.config_status_label.text(), "有未应用修改")

        page.reset_button.click()

        self.assertEqual(page.mode_combo.currentText(), "main")
        self.assertEqual(page.config_status_label.text(), "✓ 已保存配置")

    def test_runtime_page_custom_sequence_disables_smart_battle_checkbox(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.mode_combo.setCurrentText("custom_sequence")

        self.assertFalse(page.smart_battle_checkbox.isEnabled())

    def test_runtime_page_uses_switch_widgets_for_runtime_toggles(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        self.assertIsInstance(page.smart_battle_checkbox, _RuntimeToggleSwitch)
        self.assertIsInstance(page.continue_battle_checkbox, _RuntimeToggleSwitch)
        self.assertEqual(page.smart_battle_checkbox.sizeHint().width(), 54)
        self.assertEqual(page.continue_battle_checkbox.sizeHint().width(), 54)

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
        before_preview_min_hint = page.preview_label.minimumSizeHint()

        image = QImage(1920, 1080, QImage.Format.Format_RGB888)
        page.set_preview_image(image)

        self.assertEqual(page.sizeHint(), before_page_hint)
        self.assertEqual(page.preview_label.sizeHint(), before_preview_hint)
        self.assertEqual(page.preview_label.minimumSizeHint(), before_preview_min_hint)

    def test_runtime_page_matches_run_tab_layout_contract(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)
        page.resize(1600, 900)
        page.show()
        QApplication.processEvents()

        self.assertTrue(hasattr(page, "settings_column"))
        self.assertTrue(hasattr(page, "center_stage"))
        self.assertTrue(hasattr(page, "summary_column"))
        self.assertTrue(hasattr(page, "summary_card"))
        self.assertFalse(hasattr(page, "preview_log_splitter"))
        self.assertEqual(page.center_stage.layout().count(), 2)
        self.assertIs(page.center_stage.layout().itemAt(0).widget(), page.preview_card)
        self.assertIs(page.center_stage.layout().itemAt(1).widget(), page.log_card)
        self.assertEqual(len(page.findChildren(QSplitter)), 0)
        self.assertFalse(hasattr(page, "status_card"))
        self.assertFalse(hasattr(page, "status_value"))
        self.assertEqual(page.layout().spacing(), 6)
        self.assertEqual(page.settings_column.property("layoutRole"), "sidePanel")
        self.assertEqual(page.summary_column.property("layoutRole"), "sidePanel")
        self.assertLessEqual(abs(page.settings_column.width() - page.summary_column.width()), 1)
        self.assertEqual(page.settings_column.layout().spacing(), 10)
        self.assertEqual(page.summary_column.layout().spacing(), 10)
        self.assertFalse(page.log_output.isHidden())
        self.assertGreaterEqual(page.log_output.minimumHeight(), 120)
        self.assertTrue(hasattr(page, "preview_head_widget"))
        self.assertTrue(hasattr(page, "action_buttons_row"))
        action_row_layout = page.action_buttons_row.layout()
        self.assertIsNotNone(action_row_layout)
        self.assertEqual(action_row_layout.contentsMargins().top(), 2)
        self.assertEqual(action_row_layout.contentsMargins().bottom(), 2)
        self.assertEqual(action_row_layout.contentsMargins().left(), 0)
        self.assertEqual(action_row_layout.contentsMargins().right(), 0)
        self.assertEqual(action_row_layout.spacing(), 6)
        self.assertEqual(page.log_clear_button.height(), 26)
        self.assertEqual(page.log_clear_button.maximumHeight(), 26)
        self.assertEqual(page.log_popout_button.height(), 26)
        self.assertEqual(page.log_popout_button.maximumHeight(), 26)
        self.assertGreaterEqual(page.start_button.height(), 30)
        self.assertGreaterEqual(page.stop_button.height(), 30)
        self.assertEqual(page.action_buttons_row.parentWidget(), page.settings_column)
        self.assertEqual(page.start_button.parentWidget(), page.action_buttons_row)
        self.assertEqual(page.stop_button.parentWidget(), page.action_buttons_row)
        self.assertLessEqual(abs(page.start_button.width() - page.stop_button.width()), 1)
        self.assertEqual(page.config_card.parentWidget(), page.settings_column)
        config_grid = page.config_card.layout().itemAt(1).layout()
        self.assertIsNotNone(config_grid)
        mode_cell = config_grid.cellRect(0, 1)
        log_cell = config_grid.cellRect(3, 1)
        self.assertEqual(page.mode_combo.geometry().x() + page.mode_combo.width(), mode_cell.x() + mode_cell.width())
        self.assertEqual(page.log_level_combo.geometry().x() + page.log_level_combo.width(), log_cell.x() + log_cell.width())
        config_buttons_layout = page.config_card.layout().itemAt(2).layout()
        self.assertIsNotNone(config_buttons_layout)
        self.assertEqual(config_buttons_layout.count(), 2)
        self.assertEqual(config_buttons_layout.spacing(), 6)
        self.assertIs(config_buttons_layout.itemAt(0).widget(), page.apply_button)
        self.assertIs(config_buttons_layout.itemAt(1).widget(), page.reset_button)
        self.assertGreaterEqual(page.apply_button.height(), 30)
        self.assertGreaterEqual(page.reset_button.height(), 30)
        self.assertLessEqual(abs(page.apply_button.width() - page.reset_button.width()), 1)
        self.assertEqual(page.summary_card.parentWidget(), page.summary_column)
        self.assertIs(page.summary_column.layout().itemAt(0).widget(), page.summary_card)
        self.assertEqual(page.preview_head_widget.property("headerRole"), "panel")
        self.assertEqual(page.preview_head_widget.height(), 38)
        self.assertEqual(page.preview_head_widget.maximumHeight(), 38)
        self.assertEqual(page.preview_title_label.property("textRole"), "panelTitle")
        self.assertEqual(page.preview_title_label.text(), "实时画面")
        self.assertEqual(page.preview_status_value.objectName(), "runtimePreviewStatusValue")
        self.assertEqual(page.preview_status_value.height(), 26)
        self.assertEqual(page.preview_status_value.maximumHeight(), 26)
        self.assertEqual(page.preview_status_value.text(), "空闲")
        self.assertEqual(page.preview_status_value.property("statusState"), "idle")
        self.assertEqual(page.log_head_widget.property("headerRole"), "panel")
        self.assertEqual(page.log_title_label.property("textRole"), "panelTitle")
        self.assertEqual(page.preview_card.property("layoutRole"), "canvasPanel")
        self.assertEqual(page.log_card.property("layoutRole"), "canvasPanel")
        self.assertEqual(page.center_stage.layout().spacing(), 6)
        self.assertEqual(page.summary_card.property("panelRole"), "card")
        self.assertEqual(page.summary_section_label.text(), "当前已保存配置")
        self.assertEqual(page.preview_label.objectName(), "runtimePreviewViewport")
        self.assertEqual(page.preview_label.styleSheet(), "")
        self.assertEqual(page.preview_card.layout().contentsMargins().left(), 0)
        self.assertEqual(page.preview_card.layout().contentsMargins().top(), 0)
        self.assertTrue(page.preview_label.hasHeightForWidth())
        self.assertEqual(page.preview_label.sizeHint().width(), 720)
        self.assertEqual(page.preview_label.sizeHint().height(), 405)
        self.assertEqual(page.preview_label.minimumSizeHint().width(), 560)
        self.assertEqual(page.preview_label.minimumSizeHint().height(), 315)
        self.assertEqual(page.preview_label.heightForWidth(720), 405)
        self.assertEqual(page.log_output.objectName(), "runtimeLogOutput")
        self.assertEqual(page.log_output.styleSheet(), "")

    def test_runtime_page_expands_left_panel_after_capping_right_preview_width(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        page.resize(1600, 900)
        page.show()
        QApplication.processEvents()

        preview_body_height = page.preview_label.height()
        expected_center_width = int(round(preview_body_height * 16 / 9))
        total_columns_width = (
            page.settings_column.width()
            + page.summary_column.width()
            + page.center_stage.width()
            + page.layout().spacing() * 2
        )

        self.assertLessEqual(abs(page.center_stage.width() - expected_center_width), 24)
        self.assertLessEqual(abs(page.settings_column.width() - page.summary_column.width()), 1)
        self.assertLessEqual(abs(total_columns_width - page.contentsRect().width()), 2)
        self.assertEqual(
            page.preview_card.height() + page.log_card.height() + page.center_stage.layout().spacing(),
            page.center_stage.height(),
        )

    def test_runtime_page_uses_current_screen_label(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        labels = [label.text() for label in page.findChildren(QLabel)]
        self.assertNotIn("当前画面", labels)
        self.assertNotIn("当前截图", labels)

    def test_runtime_page_elides_long_summary_values_without_wrapping(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)
        support_text = "berserker/morgan/support-slot-very-long-name"
        sequence_text = "config/custom_sequences/demo_super_long_sequence_name.yaml"

        page.set_summary_text(
            "\n".join(
                [
                    "battle_mode=main",
                    "smart_battle=off",
                    "continue_battle=True",
                    "log_level=INFO",
                    f"support={support_text}",
                    f"custom_sequence={sequence_text}",
                ]
            )
        )

        self.assertFalse(page.support_value.wordWrap())
        self.assertFalse(page.sequence_value.wordWrap())
        self.assertEqual(page.support_value.maximumWidth(), 180)
        self.assertEqual(page.sequence_value.maximumWidth(), 180)
        self.assertEqual(page.support_value.toolTip(), support_text)
        self.assertEqual(page.sequence_value.toolTip(), sequence_text)
        self.assertNotEqual(page.support_value.text(), support_text)
        self.assertNotEqual(page.sequence_value.text(), sequence_text)

    def test_runtime_page_uses_shared_notice_and_status_roles(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        self.assertEqual(page.config_status_label.property("noticeRole"), "saved")
        self.assertEqual(page.preview_status_value.property("statusState"), "idle")

        page.log_level_combo.setCurrentText("DEBUG")

        self.assertEqual(page.config_status_label.property("noticeRole"), "dirty")

    def test_runtime_page_preview_header_status_tracks_lifecycle_text(self) -> None:
        controller = DummyRuntimeController()
        page = RuntimePage(controller)

        controller.lifecycle_changed.emit("运行中")

        self.assertEqual(page.preview_status_value.text(), "运行中")
        self.assertEqual(page.preview_status_value.property("statusState"), "running")

    def test_runtime_controller_missing_config_stays_constructible_and_reports_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "battle_config.yaml"
            controller = AutomationRuntimeController(
                config_path=missing_path,
                worker_factory=lambda _path: (_ for _ in ()).throw(AssertionError("should not create worker")),
            )
            summaries: list[str] = []
            lifecycles: list[str] = []
            failures: list[str] = []
            controller.summary_changed.connect(summaries.append)
            controller.lifecycle_changed.connect(lifecycles.append)
            controller.error_occurred.connect(failures.append)

            controller.refresh_summary()

            self.assertFalse(controller.config_available)
            self.assertEqual(controller.current_summary, controller.CONFIG_UNAVAILABLE_SUMMARY)
            self.assertIn("battle_config.yaml", controller.current_config_error or "")
            self.assertEqual(controller.current_lifecycle_text, "故障")
            self.assertEqual(summaries[-1], controller.CONFIG_UNAVAILABLE_SUMMARY)
            self.assertEqual(lifecycles[-1], controller.current_lifecycle_text)
            self.assertEqual(failures[-1], controller.current_config_error)

    def test_runtime_page_disables_all_runtime_controls_when_config_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "battle_config.yaml"
            controller = AutomationRuntimeController(config_path=missing_path)

            page = RuntimePage(controller)
            page.start_button.click()

            self.assertEqual(page.preview_status_value.text(), "故障")
            self.assertNotIn("battle_config.yaml", page.preview_status_value.text())
            self.assertFalse(page.start_button.isEnabled())
            self.assertFalse(page.stop_button.isEnabled())
            self.assertFalse(page.apply_button.isEnabled())
            self.assertFalse(page.reset_button.isEnabled())
            self.assertFalse(page.mode_combo.isEnabled())
            self.assertFalse(page.smart_battle_checkbox.isEnabled())
            self.assertFalse(page.continue_battle_checkbox.isEnabled())
            self.assertFalse(page.log_level_combo.isEnabled())
            self.assertEqual(page.config_status_label.text(), controller.current_config_error)
            self.assertEqual(page.mode_value.text(), "配置不可用")

    def test_runtime_page_recovers_after_config_file_is_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "battle_config.yaml"
            controller = AutomationRuntimeController(config_path=config_path)
            page = RuntimePage(controller)
            valid_config = {
                "battle_mode": "main",
                "continue_battle": False,
                "log_level": "DEBUG",
                "support": {
                    "class_name": "berserker",
                    "servant": "morgan",
                },
                "smart_battle": {
                    "enabled": True,
                },
                "custom_sequence_battle": {
                    "sequence": "demo.yaml",
                },
            }
            config_path.write_text(
                yaml.safe_dump(valid_config, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

            controller.refresh_summary()

            self.assertTrue(controller.config_available)
            self.assertEqual(page.preview_status_value.text(), "空闲")
            self.assertTrue(page.start_button.isEnabled())
            self.assertTrue(page.mode_combo.isEnabled())
            self.assertTrue(page.smart_battle_checkbox.isEnabled())
            self.assertTrue(page.continue_battle_checkbox.isEnabled())
            self.assertTrue(page.log_level_combo.isEnabled())
            self.assertEqual(page.mode_value.text(), "main")
            self.assertEqual(page.log_level_value.text(), "DEBUG")


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


class RuntimeWorkerTests(unittest.TestCase):
    def test_controller_sets_stopping_state_and_suppresses_failure_after_manual_stop(self) -> None:
        ensure_qt_application()
        worker = FakeManagedWorker()
        lifecycles: list[str] = []
        failures: list[str] = []

        controller = AutomationRuntimeController(
            worker_factory=lambda _path: worker,
        )
        controller.lifecycle_changed.connect(lifecycles.append)
        controller.error_occurred.connect(failures.append)

        controller.start()
        worker.run_started.emit()
        controller.stop()
        worker.run_failed.emit("boom")
        worker.finish()

        self.assertEqual(worker.start_calls, 1)
        self.assertEqual(worker.stop_calls, 1)
        self.assertIn("停止中", lifecycles)
        self.assertEqual(failures, [])
        self.assertEqual(lifecycles[-1], "已停止")

    def test_worker_escalates_from_terminate_to_kill_after_stop_deadlines(self) -> None:
        worker = AutomationRuntimeWorker("config/battle_config.yaml")
        process = FakeRuntimeProcess()

        worker._process = process
        worker._stop_requested = True
        worker._terminate_sent = False
        worker._kill_sent = False
        worker._terminate_deadline = 10.0
        worker._kill_deadline = 11.5

        worker._enforce_stop_deadlines(9.5)
        worker._enforce_stop_deadlines(10.0)
        worker._enforce_stop_deadlines(11.5)

        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 1)

    def test_worker_emits_started_after_runtime_assembly_begins_running(self) -> None:
        class DummyEngine:
            def run(self) -> None:
                return None

        class DummyAdb:
            serial = "emulator-5560"

        class DummyAssembly:
            adb = DummyAdb()
            engine = DummyEngine()

        with patch(
            "core.gui.runtime.worker_process.build_runtime_assembly",
            return_value=DummyAssembly(),
        ):
            worker_process = __import__(
                "core.gui.runtime.worker_process",
                fromlist=["run_runtime_process"],
            )
            events: list[dict[str, object]] = []

            class _Queue:
                def put(self, item):
                    events.append(item)

                def get(self, timeout=None):
                    raise queue.Empty

            worker_process.run_runtime_process(
                config_path="config/battle_config.yaml",
                event_queue=_Queue(),
                control_queue=_Queue(),
            )

        self.assertIn(
            {"type": "started"},
            events,
        )
