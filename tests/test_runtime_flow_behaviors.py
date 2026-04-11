import unittest
from unittest.mock import Mock, patch

import numpy as np

from core.perception.image_recognizer import TemplateMatchResult
from core.perception.state_detector import StateDetector
from core.runtime.battle_flow import BattleFlowMixin
from core.runtime.support_flow import SupportFlowMixin
from core.shared.game_types import GameState
from core.shared.resource_catalog import ResourceCatalog
from core.shared.screen_coordinates import GameCoordinates


class DummySupportFlow(SupportFlowMixin):
    SUPPORT_ENTRY_BUFFER_WAIT = 2.0

    def __init__(self) -> None:
        self.config = Mock()
        self.config.support_config.return_value = {
            "class_name": "berserker",
            "servant": "",
            "pick_index": 1,
            "max_scroll_pages": 3,
        }
        self.selected_support_class = None
        self.fallback_pick_index = None

    def _select_support_class(self, support_class: str) -> None:
        self.selected_support_class = support_class

    def _fallback_pick_support(self, pick_index: int) -> None:
        self.fallback_pick_index = pick_index


class DummyBattleFlow(BattleFlowMixin):
    DEFAULT_CLICK_DELAY = 0.5

    def __init__(self, stage: int | None, next_click_result: bool = True) -> None:
        self._stage = stage
        self._click_template_result = next_click_result
        self._loop_done = 0
        self._battle_actions_done = True
        self._used_servant_skills = {1, 2, 3}
        self._last_wave_index = 3
        self._last_enemy_count = 1
        self._last_current_turn = 5
        self._last_processed_turn = 5
        self.adb = Mock()
        self.clicked_templates: list[tuple[str, str]] = []

    def _detect_battle_result_stage(self) -> int | None:
        return self._stage

    def _click_template(self, template_name: str, success_message: str) -> bool:
        self.clicked_templates.append((template_name, success_message))
        return self._click_template_result


class FakeRecognizer:
    def match_with_score(
        self, template_path: str, screen: np.ndarray
    ) -> TemplateMatchResult:
        if template_path.endswith("fight_result_2.png"):
            return TemplateMatchResult(score=0.92, position=(10, 10))
        return TemplateMatchResult(score=0.0, position=None)


class RuntimeFlowBehaviorTest(unittest.TestCase):
    def test_support_select_waits_for_list_to_settle_before_filtering(self) -> None:
        flow = DummySupportFlow()

        with patch("core.runtime.support_flow.time.sleep") as sleep_mock:
            flow.handle_support_select()

        sleep_mock.assert_called_once_with(2.0)
        self.assertEqual(flow.selected_support_class, "berserker")
        self.assertEqual(flow.fallback_pick_index, 1)

    def test_battle_result_stage_one_clicks_continue_without_finishing_battle(self) -> None:
        flow = DummyBattleFlow(stage=1)

        with patch("core.runtime.battle_flow.time.sleep") as sleep_mock:
            flow.handle_battle_result()

        flow.adb.click.assert_called_once_with(*GameCoordinates.RESULT_CONTINUE)
        sleep_mock.assert_called_once_with(flow.DEFAULT_CLICK_DELAY)
        self.assertEqual(flow._loop_done, 0)
        self.assertTrue(flow._battle_actions_done)
        self.assertEqual(flow._used_servant_skills, {1, 2, 3})

    def test_battle_result_stage_three_clicks_next_and_marks_battle_complete(self) -> None:
        flow = DummyBattleFlow(stage=3, next_click_result=True)

        with patch("core.runtime.battle_flow.time.sleep") as sleep_mock:
            flow.handle_battle_result()

        self.assertEqual(
            flow.clicked_templates,
            [("next.png", "已点击结算页下一步")],
        )
        sleep_mock.assert_called_once_with(1.0)
        self.assertEqual(flow._loop_done, 1)
        self.assertFalse(flow._battle_actions_done)
        self.assertEqual(flow._used_servant_skills, set())
        self.assertIsNone(flow._last_wave_index)
        self.assertIsNone(flow._last_enemy_count)
        self.assertIsNone(flow._last_current_turn)
        self.assertIsNone(flow._last_processed_turn)

    def test_state_detector_accepts_multiple_templates_for_battle_result(self) -> None:
        resources = ResourceCatalog()
        detector = StateDetector(
            recognizer=FakeRecognizer(),
            screen_callback=lambda: "dummy_screen.png",
            resources=resources,
            screen_array_callback=lambda: np.zeros((10, 10), dtype=np.uint8),
        )

        result = detector.detect()

        self.assertEqual(result.state, GameState.BATTLE_RESULT)
        self.assertTrue(str(result.matched_template).endswith("fight_result_2.png"))


if __name__ == "__main__":
    unittest.main()
