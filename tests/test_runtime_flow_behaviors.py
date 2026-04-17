import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from core.command_card_recognition import (
    CommandCardInfo,
    CommandCardPrediction,
    CommandCardScore,
    CommandCardTrace,
)
from core.perception.battle_ocr import ServantNpStatus
from core.perception.image_recognizer import TemplateMatchResult
from core.perception.state_detector import StateDetectionResult, StateDetector
from core.runtime.handlers.battle_ready import BattleReadyHandler
from core.runtime.handlers.battle_result import BattleResultHandler
from core.runtime.handlers.card_select import CardSelectHandler
from core.runtime.handlers.loading import LoadingHandler
from core.runtime.handlers.support_select import SupportSelectHandler
from core.runtime.handlers.unknown import UnknownHandler
from core.runtime.waiter import Waiter
from core.shared.config_models import SupportConfig, SupportRecognitionConfig
from core.shared.game_types import GameState
from core.shared.resource_catalog import ResourceCatalog
from core.shared.screen_coordinates import GameCoordinates


class DummyWaiter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []
        self.stable_calls: list[dict[str, object]] = []
        self.confirm_calls: list[GameState] = []
        self.template_disappear_calls: list[dict[str, object]] = []

    def wait_seconds(self, reason: str, seconds: float) -> None:
        self.calls.append((reason, seconds))

    def confirm_state_entry(self, state: GameState) -> bool:
        self.confirm_calls.append(state)
        return True

    def wait_screen_stable(
        self,
        *,
        region=None,
        stable_frames=2,
        timeout: float,
        poll_interval: float,
    ) -> bool:
        self.stable_calls.append(
            {
                "region": region,
                "stable_frames": stable_frames,
                "timeout": timeout,
                "poll_interval": poll_interval,
            }
        )
        return True

    def wait_template_disappear(
        self,
        template_path: str,
        *,
        timeout: float,
        poll_interval: float,
    ) -> bool:
        self.template_disappear_calls.append(
            {
                "template_path": template_path,
                "timeout": timeout,
                "poll_interval": poll_interval,
            }
        )
        return True


class DummySupportSession:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            support=SupportConfig(
                class_name="berserker",
                servant="",
                pick_index=1,
                max_scroll_pages=3,
                recognition=SupportRecognitionConfig(),
            )
        )


class DummySupportHandler(SupportSelectHandler):
    def __init__(self) -> None:
        self.waiter = DummyWaiter()
        self.session = DummySupportSession()
        self.selected_support_class = None
        self.fallback_pick_index = None

    def _select_support_class(self, support_class: str) -> None:
        self.selected_support_class = support_class

    def _fallback_pick_support(self, pick_index: int) -> None:
        self.fallback_pick_index = pick_index


class DummyBattleReadySession:
    def __init__(
        self,
        *,
        default_skill_target: int = 3,
        smart_battle_enabled: bool = False,
    ) -> None:
        self.config = Mock()
        self.config.battle_mode = "main"
        self.config.default_skill_target = default_skill_target
        self.config.battle_actions.return_value = [
            {"type": "servant", "skill": 1, "target": None}
        ]
        self.battle = Mock()
        self.recognizer = Mock()
        self.recognizer.match.return_value = (200, 300)
        self.resources = Mock()
        self.resources.template.side_effect = lambda name, category="ui": name
        self.battle_actions_done = False
        self.smart_battle_enabled = smart_battle_enabled

    def refresh_screen(self) -> str:
        return "screen.png"

    def get_latest_screen_image(self) -> np.ndarray:
        return np.zeros((10, 10), dtype=np.uint8)


class DummyBattleReadyHandler(BattleReadyHandler):
    def __init__(
        self,
        *,
        default_skill_target: int = 3,
        smart_battle_enabled: bool = False,
    ) -> None:
        self.waiter = DummyWaiter()
        self.session = DummyBattleReadySession(
            default_skill_target=default_skill_target,
            smart_battle_enabled=smart_battle_enabled,
        )


class DummyCustomBattleReadySession:
    def __init__(
        self,
        *,
        wave: int | None,
        turn: int | None,
        plan=None,
        recognizer_matches: list[object | None] | None = None,
    ) -> None:
        self.config = Mock()
        self.config.battle_mode = "custom_sequence"
        self.config.custom_sequence_battle.find_turn_plan.return_value = plan
        self.battle_snapshot_reader = Mock()
        self.battle_snapshot_reader.read_snapshot.return_value = SimpleNamespace(
            wave_index=wave,
            current_turn=turn,
        )
        self.battle = Mock()
        self.recognizer = Mock()
        self.recognizer.match.side_effect = recognizer_matches or []
        self.resources = Mock()
        self.resources.template.side_effect = lambda name, category="ui": name
        self.latest_screen_rgb = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.latest_screen_image = np.zeros((10, 10), dtype=np.uint8)
        self.active_custom_turn_plan = None
        self.last_processed_custom_turn = None
        self.smart_battle_enabled = False
        self.battle_actions_done = False

    @property
    def custom_sequence_enabled(self) -> bool:
        return True

    def refresh_screen(self) -> str:
        return "screen.png"

    def get_latest_screen_image(self) -> np.ndarray:
        return self.latest_screen_image

    def get_latest_screen_rgb(self) -> np.ndarray:
        return self.latest_screen_rgb


class DummyCustomBattleReadyHandler(BattleReadyHandler):
    def __init__(
        self,
        *,
        wave: int | None,
        turn: int | None,
        plan=None,
        recognizer_matches: list[object | None] | None = None,
    ) -> None:
        self.waiter = DummyWaiter()
        self.session = DummyCustomBattleReadySession(
            wave=wave,
            turn=turn,
            plan=plan,
            recognizer_matches=recognizer_matches,
        )


class DummyBattleSession:
    def __init__(
        self,
        *,
        continue_battle: bool = True,
        smart_battle_enabled: bool = False,
    ) -> None:
        self.adb = Mock()
        self.recognizer = Mock()
        self.resources = Mock()
        self.resources.template.side_effect = lambda name, category="ui": name
        self.config = SimpleNamespace(
            continue_battle=continue_battle,
            battle_mode="main",
            smart_battle=SimpleNamespace(enabled=smart_battle_enabled),
        )
        self._screen = np.zeros((10, 10), dtype=np.uint8)
        self.loop_done = 0
        self.battle_actions_done = True
        self.used_servant_skills = {1, 2, 3}
        self.last_wave_index = 3
        self.last_enemy_count = 1
        self.last_current_turn = 5
        self.last_processed_turn = 5
        self.pending_custom_nobles: list[int] = []
        self.stop_requested = False
        self.smart_battle_enabled = smart_battle_enabled

    def get_latest_screen_image(self) -> np.ndarray:
        return self._screen

    def refresh_screen(self) -> str:
        return "screen.png"

    def mark_battle_result_complete(self) -> None:
        self.loop_done += 1
        self.battle_actions_done = False
        self.used_servant_skills.clear()
        self.last_wave_index = None
        self.last_enemy_count = None
        self.last_current_turn = None
        self.last_processed_turn = None
        self.pending_custom_nobles = []


class DummyBattleResultHandler(BattleResultHandler):
    def __init__(
        self,
        stage: int | None,
        *,
        continue_battle: bool = True,
        smart_battle_enabled: bool = False,
    ) -> None:
        self.waiter = DummyWaiter()
        self.session = DummyBattleSession(
            continue_battle=continue_battle,
            smart_battle_enabled=smart_battle_enabled,
        )
        self.session.recognizer.match.return_value = (321, 654)
        self._stage = stage

    def _detect_battle_result_stage(self) -> int | None:
        return self._stage


class DummyCardSelectSession:
    def __init__(
        self,
        prediction: CommandCardPrediction | None = None,
        *,
        smart_battle_enabled: bool = False,
    ) -> None:
        self.config = Mock()
        self.config.battle_mode = "main"
        self.config.ocr = Mock()
        self.config.ocr.retry_once_on_low_confidence = False
        self._prediction = prediction
        self.saved_predictions: list[CommandCardPrediction] = []
        self.saved_rgb_frames: list[np.ndarray] = []
        self.last_current_turn = 2
        self.last_wave_index = 1
        self.active_custom_turn_plan = None
        self.battle = Mock()
        self.adb = Mock()
        self.smart_battle_enabled = smart_battle_enabled

    def command_card_priority(self) -> list[str]:
        return [
            "caster/zhuge_liang",
            "caster/merlin",
            "berserker/morgan",
        ]

    def frontline_servant_names(self) -> list[str]:
        return [
            "caster/zhuge_liang",
            "caster/merlin",
            "berserker/morgan",
        ]

    def support_attacker_servant_name(self) -> str | None:
        return "berserker/morgan"

    def get_latest_screen_rgb(self) -> np.ndarray:
        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    def get_command_card_recognizer(self):
        prediction = self._prediction

        class _Recognizer:
            def analyze_frontline(self, screen_rgb, frontline_servants, *, support_attacker):
                return prediction

        return _Recognizer()

    def save_command_card_evidence(
        self,
        prediction: CommandCardPrediction,
        screen_rgb: np.ndarray,
    ) -> tuple[str, str, str]:
        self.saved_predictions.append(prediction)
        self.saved_rgb_frames.append(screen_rgb)
        return ("frame.png", "frame_masked.png", "frame.json")


class DummyLoadingSession:
    def __init__(self) -> None:
        self.resources = Mock()
        self.resources.template.return_value = "tips-template"


class DummyUnknownSession:
    def __init__(self, *, click_result: bool = False) -> None:
        self.recognizer = Mock()
        self.resources = Mock()
        self.resources.template.side_effect = lambda name, category="ui": name
        self._screen = np.zeros((10, 10), dtype=np.uint8)
        self.adb = Mock()
        self.recognizer.match.return_value = (321, 654) if click_result else None
        self.unknown_snapshot_saved = False
        self.consecutive_unknown_count = 0

    def get_latest_screen_image(self) -> np.ndarray:
        return self._screen

    def save_unknown_snapshot(self) -> str:
        return "unknown.png"


class DummyCardSelectHandler(CardSelectHandler):
    def __init__(
        self,
        prediction: CommandCardPrediction | None = None,
        *,
        smart_battle_enabled: bool = False,
    ) -> None:
        self.waiter = DummyWaiter()
        self.session = DummyCardSelectSession(
            prediction,
            smart_battle_enabled=smart_battle_enabled,
        )
        self.call_order: list[str] = []

    def _read_np_statuses_with_retry(self):
        self.call_order.append("read_np")
        return []

    def _read_command_cards(self):
        self.call_order.append("read_cards")
        return super()._read_command_cards()

    def build_card_plan(self, np_statuses, card_owners=None, cards=None):
        self.call_order.append("build_plan")
        return []

    def execute_card_plan(self, card_plan):
        self.call_order.append("execute_plan")

    def _wait_after_card_plan(self) -> None:
        self.call_order.append("wait_after_plan")


class DummyCustomCardSelectSession:
    def __init__(
        self,
        *,
        nobles: list[int] | None = None,
        colors: list[str | None] | None = None,
        np_statuses: list[ServantNpStatus] | None = None,
        recognized_cards: list[CommandCardInfo] | None = None,
        pending_nobles: list[int] | None = None,
    ) -> None:
        self.config = Mock()
        self.config.battle_mode = "custom_sequence"
        self.config.ocr = Mock()
        self.config.ocr.retry_once_on_low_confidence = False
        self.active_custom_turn_plan = (
            SimpleNamespace(nobles=nobles or []) if nobles is not None else None
        )
        self._colors = colors or ["arts", "arts", "arts", "quick", "buster"]
        self._np_statuses = np_statuses or []
        self._recognized_cards = recognized_cards
        self.pending_custom_nobles = list(pending_nobles or [])
        self.battle = Mock()
        self.adb = Mock()

    @property
    def custom_sequence_enabled(self) -> bool:
        return True

    def read_np_statuses(self) -> list[ServantNpStatus]:
        return self._np_statuses

    def command_card_priority(self) -> list[str]:
        return [
            "caster/zhuge_liang",
            "caster/merlin",
            "berserker/morgan",
        ]

    def frontline_servant_names(self) -> list[str]:
        return [
            "caster/zhuge_liang",
            "caster/merlin",
            "berserker/morgan",
        ]

    def support_attacker_servant_name(self) -> str | None:
        return "berserker/morgan"

    def get_latest_screen_rgb(self) -> np.ndarray:
        return np.zeros((1080, 1920, 3), dtype=np.uint8)


class DummyCustomCardSelectHandler(CardSelectHandler):
    def __init__(
        self,
        *,
        nobles: list[int] | None = None,
        colors: list[str | None] | None = None,
        np_statuses: list[ServantNpStatus] | None = None,
        recognized_cards: list[CommandCardInfo] | None = None,
        pending_nobles: list[int] | None = None,
    ) -> None:
        self.waiter = DummyWaiter()
        self.session = DummyCustomCardSelectSession(
            nobles=nobles,
            colors=colors,
            np_statuses=np_statuses,
            recognized_cards=recognized_cards,
            pending_nobles=pending_nobles,
        )
        self.executed_plan = None

    def _read_np_statuses_with_retry(self):
        return self.session.read_np_statuses()

    def _read_custom_color_cards(self) -> list[CommandCardInfo]:
        return [
            CommandCardInfo(index=index + 1, owner=None, color=color)
            for index, color in enumerate(self.session._colors)
        ]

    def _read_command_cards(self):
        if self.session._recognized_cards is None:
            return None, None
        return self.session._recognized_cards, None

    def execute_card_plan(self, card_plan):
        self.executed_plan = card_plan

    def _wait_after_card_plan(self) -> None:
        return None


def _make_prediction(*, low_confidence: bool) -> CommandCardPrediction:
    traces = [
        CommandCardTrace(
            index=1,
            owner="caster/zhuge_liang",
            color="arts",
            score=0.40,
            margin=0.10,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore("caster/zhuge_liang", 0.40),
                CommandCardScore("caster/merlin", 0.21),
                CommandCardScore("berserker/morgan", 0.11),
            ],
        ),
        CommandCardTrace(
            index=2,
            owner="caster/merlin",
            color="quick",
            score=0.38,
            margin=0.08,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore("caster/merlin", 0.38),
                CommandCardScore("caster/zhuge_liang", 0.30),
                CommandCardScore("berserker/morgan", 0.19),
            ],
        ),
        CommandCardTrace(
            index=3,
            owner=None if low_confidence else "berserker/morgan",
            color="buster",
            score=0.05 if low_confidence else 0.42,
            margin=0.001 if low_confidence else 0.09,
            support_badge=False,
            low_confidence=low_confidence,
            scores=[
                CommandCardScore("berserker/morgan", 0.05 if low_confidence else 0.42),
                CommandCardScore("caster/merlin", 0.049 if low_confidence else 0.21),
                CommandCardScore("caster/zhuge_liang", 0.04 if low_confidence else 0.18),
            ],
        ),
        CommandCardTrace(
            index=4,
            owner="caster/zhuge_liang",
            color="arts",
            score=0.36,
            margin=0.06,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore("caster/zhuge_liang", 0.36),
                CommandCardScore("caster/merlin", 0.22),
                CommandCardScore("berserker/morgan", 0.10),
            ],
        ),
        CommandCardTrace(
            index=5,
            owner="caster/merlin",
            color="quick",
            score=0.37,
            margin=0.07,
            support_badge=False,
            low_confidence=False,
            scores=[
                CommandCardScore("caster/merlin", 0.37),
                CommandCardScore("caster/zhuge_liang", 0.23),
                CommandCardScore("berserker/morgan", 0.12),
            ],
        ),
    ]
    return CommandCardPrediction(
        frontline_servants=[
            "caster/zhuge_liang",
            "caster/merlin",
            "berserker/morgan",
        ],
        support_attacker="berserker/morgan",
        traces=traces,
        min_score=0.07,
        min_margin=0.002,
        joint_score=0.38,
        joint_margin=0.05,
        joint_low_confidence=False,
    )


def _make_joint_low_confidence_prediction() -> CommandCardPrediction:
    prediction = _make_prediction(low_confidence=False)
    return CommandCardPrediction(
        frontline_servants=prediction.frontline_servants,
        support_attacker=prediction.support_attacker,
        traces=prediction.traces,
        min_score=prediction.min_score,
        min_margin=prediction.min_margin,
        joint_score=0.31,
        joint_margin=0.001,
        joint_low_confidence=True,
        assignment_candidates=[],
    )


class DummyLoadingHandler(LoadingHandler):
    def __init__(self) -> None:
        self.waiter = DummyWaiter()
        self.session = DummyLoadingSession()


class RecordingStateEntryWaiter(Waiter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []
        self.stable_calls: list[dict[str, object]] = []

    def wait_seconds(self, reason: str, seconds: float) -> None:
        self.calls.append((reason, seconds))

    def wait_screen_stable(
        self,
        *,
        region=None,
        stable_frames=2,
        timeout: float,
        poll_interval: float,
    ) -> bool:
        self.stable_calls.append(
            {
                "region": region,
                "stable_frames": stable_frames,
                "timeout": timeout,
                "poll_interval": poll_interval,
            }
        )
        return True


class FakeRecognizer:
    def match_with_score(
        self, template_path: str, screen: np.ndarray
    ) -> TemplateMatchResult:
        if template_path.endswith("fight_result_2.png"):
            return TemplateMatchResult(score=0.92, position=(10, 10))
        return TemplateMatchResult(score=0.0, position=None)


class RuntimeFlowBehaviorTest(unittest.TestCase):
    def test_battle_ready_uses_configured_default_skill_target(self) -> None:
        handler = DummyBattleReadyHandler(default_skill_target=2)

        handler.handle()

        handler.session.battle.click_servant_skill.assert_called_once_with(1)
        handler.session.battle.select_servant_target.assert_called_once_with(2)
        handler.session.battle.finish_servant_skill.assert_called_once_with(1, target=2)
        handler.session.battle.attack.assert_called_once_with()

    def test_smart_battle_v001_uses_skill_sequence_on_first_turn(self) -> None:
        handler = DummyBattleReadyHandler(
            default_skill_target=2,
            smart_battle_enabled=True,
        )

        handler.handle()

        handler.session.battle.click_servant_skill.assert_called_once_with(1)
        handler.session.battle.select_servant_target.assert_called_once_with(2)
        handler.session.battle.finish_servant_skill.assert_called_once_with(1, target=2)
        handler.session.battle.attack.assert_called_once_with()

    def test_custom_sequence_battle_ready_executes_turn_actions_and_attacks(self) -> None:
        plan = SimpleNamespace(
            actions=[
                SimpleNamespace(type="enemy_target", target=2),
                SimpleNamespace(type="servant_skill", actor=1, skill=1, target=None),
                SimpleNamespace(type="servant_skill", actor=2, skill=3, target=1),
            ],
            nobles=[3],
        )
        handler = DummyCustomBattleReadyHandler(
            wave=1,
            turn=1,
            plan=plan,
            recognizer_matches=[None, (200, 300)],
        )

        handler.handle()

        handler.session.battle.select_enemy_target.assert_called_once_with(2)
        handler.session.battle.click_servant_skill.assert_any_call(1)
        handler.session.battle.finish_servant_skill.assert_any_call(1)
        handler.session.battle.click_servant_skill.assert_any_call(6)
        handler.session.battle.select_servant_target.assert_called_once_with(1)
        handler.session.battle.finish_servant_skill.assert_any_call(6, target=1)
        handler.session.battle.attack.assert_called_once_with()
        self.assertIs(handler.session.active_custom_turn_plan, plan)
        self.assertEqual(handler.session.last_processed_custom_turn, (1, 1))

    def test_custom_sequence_battle_ready_without_plan_attacks_directly(self) -> None:
        handler = DummyCustomBattleReadyHandler(wave=1, turn=2, plan=None)

        handler.handle()

        handler.session.battle.select_enemy_target.assert_not_called()
        handler.session.battle.click_servant_skill.assert_not_called()
        handler.session.battle.attack.assert_called_once_with()
        self.assertIsNone(handler.session.active_custom_turn_plan)
        self.assertEqual(handler.session.last_processed_custom_turn, (1, 2))

    def test_custom_sequence_battle_ready_stops_when_wave_or_turn_missing(self) -> None:
        handler = DummyCustomBattleReadyHandler(wave=None, turn=1, plan=None)

        with self.assertRaises(RuntimeError):
            handler.handle()

        handler.session.battle.attack.assert_not_called()

    def test_custom_sequence_battle_ready_skips_duplicate_turn_actions(self) -> None:
        plan = SimpleNamespace(actions=[SimpleNamespace(type="enemy_target", target=2)], nobles=[])
        handler = DummyCustomBattleReadyHandler(wave=1, turn=1, plan=plan)
        handler.session.active_custom_turn_plan = plan
        handler.session.last_processed_custom_turn = (1, 1)

        handler.handle()

        handler.session.battle.select_enemy_target.assert_not_called()
        handler.session.battle.attack.assert_called_once_with()

    def test_support_select_waits_for_list_to_settle_before_filtering(self) -> None:
        handler = DummySupportHandler()

        handler.handle()

        self.assertEqual(handler.waiter.confirm_calls, [GameState.SUPPORT_SELECT])
        self.assertEqual(handler.selected_support_class, "berserker")
        self.assertEqual(handler.fallback_pick_index, 1)

    def test_battle_result_stage_one_clicks_continue_without_finishing_battle(self) -> None:
        handler = DummyBattleResultHandler(stage=1)

        handler.handle()

        handler.session.adb.click.assert_called_once_with(*GameCoordinates.RESULT_CONTINUE)
        self.assertEqual(handler.waiter.confirm_calls, [GameState.BATTLE_RESULT])
        self.assertEqual(handler.waiter.calls, [("已点击结算页第 1 段继续", 0.5)])
        self.assertEqual(handler.waiter.stable_calls, [])
        self.assertEqual(handler.session.loop_done, 0)
        self.assertTrue(handler.session.battle_actions_done)
        self.assertEqual(handler.session.used_servant_skills, {1, 2, 3})

    def test_battle_result_stage_three_clicks_next_and_marks_battle_complete(self) -> None:
        handler = DummyBattleResultHandler(stage=3)
        handler.session.recognizer.match.side_effect = (
            lambda template_path, screen: {
                "next.png": (321, 654),
            }.get(template_path)
        )

        handler.handle()

        self.assertEqual(handler.waiter.confirm_calls, [GameState.BATTLE_RESULT])
        self.assertEqual(
            handler.session.recognizer.match.call_args_list,
            [
                unittest.mock.call("next.png", handler.session.get_latest_screen_image()),
                unittest.mock.call(
                    "continue_battle.png",
                    handler.session.get_latest_screen_image(),
                ),
            ],
        )
        handler.session.adb.click_raw.assert_called_once_with(321, 654)
        self.assertEqual(
            handler.waiter.calls,
            [("已点击结算页下一步", 0.5), ("等待结算完成收尾", 1.0)],
        )
        self.assertEqual(handler.waiter.stable_calls, [])
        self.assertEqual(handler.session.loop_done, 1)
        self.assertFalse(handler.session.battle_actions_done)
        self.assertEqual(handler.session.used_servant_skills, set())
        self.assertIsNone(handler.session.last_wave_index)
        self.assertIsNone(handler.session.last_enemy_count)
        self.assertIsNone(handler.session.last_current_turn)
        self.assertIsNone(handler.session.last_processed_turn)

    def test_battle_result_stage_three_clicks_continue_battle_when_enabled(self) -> None:
        handler = DummyBattleResultHandler(stage=3, continue_battle=True)
        handler.session.recognizer.match.side_effect = (
            lambda template_path, screen: {
                "next.png": (321, 654),
                "continue_battle.png": (777, 888),
            }.get(template_path)
        )

        handler.handle()

        self.assertEqual(
            handler.session.adb.click_raw.call_args_list,
            [
                unittest.mock.call(321, 654),
                unittest.mock.call(777, 888),
            ],
        )
        self.assertEqual(
            handler.waiter.calls,
            [
                ("已点击结算页下一步", 0.5),
                ("等待结算完成收尾", 1.0),
                ("已点击连续出击", 0.5),
            ],
        )
        self.assertEqual(handler.session.loop_done, 1)

    def test_battle_result_stage_three_stops_after_next_in_smart_battle(self) -> None:
        handler = DummyBattleResultHandler(
            stage=3,
            continue_battle=True,
            smart_battle_enabled=True,
        )
        handler.session.recognizer.match.side_effect = (
            lambda template_path, screen: {
                "next.png": (321, 654),
                "continue_battle.png": (777, 888),
            }.get(template_path)
        )

        handler.handle()

        self.assertEqual(
            handler.session.adb.click_raw.call_args_list,
            [unittest.mock.call(321, 654)],
        )
        self.assertTrue(handler.session.stop_requested)
        self.assertEqual(handler.session.loop_done, 1)

    def test_battle_result_stage_three_handles_ap_recovery_after_continue_battle(self) -> None:
        handler = DummyBattleResultHandler(stage=3, continue_battle=True)
        handler.session.recognizer.match.side_effect = (
            lambda template_path, screen: {
                "next.png": (321, 654),
                "continue_battle.png": (777, 888),
                "ap_recovery.png": (500, 500),
                "bronzed_cobalt_fruit.png": (620, 710),
                "confirm.png": (1100, 720),
            }.get(template_path)
        )

        handler.handle()

        self.assertEqual(
            handler.session.adb.click_raw.call_args_list,
            [
                unittest.mock.call(321, 654),
                unittest.mock.call(777, 888),
                unittest.mock.call(1525, 747),
                unittest.mock.call(620, 710),
                unittest.mock.call(1100, 720),
            ],
        )
        self.assertEqual(
            handler.waiter.calls,
            [
                ("已点击结算页下一步", 0.5),
                ("等待结算完成收尾", 1.0),
                ("已点击连续出击", 0.5),
                ("已将行动力恢复列表滚到底部", 0.5),
                ("已点击青铜果实", 0.5),
                ("已确认行动力恢复", 0.5),
            ],
        )
        self.assertEqual(handler.session.loop_done, 1)

    def test_battle_result_stage_three_stops_when_bronze_fruit_cannot_confirm(self) -> None:
        handler = DummyBattleResultHandler(stage=3, continue_battle=True)
        handler.session.recognizer.match.side_effect = (
            lambda template_path, screen: {
                "next.png": (321, 654),
                "continue_battle.png": (777, 888),
                "ap_recovery.png": (500, 500),
                "bronzed_cobalt_fruit.png": (620, 710),
            }.get(template_path)
        )

        with self.assertRaisesRegex(RuntimeError, "青铜果实数量不足"):
            handler.handle()

        self.assertEqual(
            handler.session.adb.click_raw.call_args_list,
            [
                unittest.mock.call(321, 654),
                unittest.mock.call(777, 888),
                unittest.mock.call(1525, 747),
                unittest.mock.call(620, 710),
            ],
        )
        self.assertEqual(handler.session.loop_done, 0)

    def test_battle_result_stage_three_clicks_close_when_continue_battle_disabled(
        self,
    ) -> None:
        handler = DummyBattleResultHandler(stage=3, continue_battle=False)
        handler.session.recognizer.match.side_effect = (
            lambda template_path, screen: {
                "next.png": (321, 654),
                "continue_battle.png": (777, 888),
                "close.png": (111, 222),
            }.get(template_path)
        )

        handler.handle()

        self.assertEqual(
            handler.session.adb.click_raw.call_args_list,
            [
                unittest.mock.call(321, 654),
                unittest.mock.call(111, 222),
            ],
        )
        self.assertEqual(
            handler.waiter.calls,
            [
                ("已点击结算页下一步", 0.5),
                ("等待结算完成收尾", 1.0),
                ("已关闭连续出击界面", 0.5),
            ],
        )
        self.assertEqual(handler.session.loop_done, 1)

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

    def test_card_select_waits_for_command_cards_to_settle_before_reading(self) -> None:
        handler = DummyCardSelectHandler(_make_prediction(low_confidence=False))

        handler.handle()

        self.assertEqual(handler.waiter.confirm_calls, [GameState.CARD_SELECT])
        self.assertEqual(
            handler.call_order,
            [
                "read_np",
                "read_cards",
                "build_plan",
                "execute_plan",
                "wait_after_plan",
            ],
        )
        self.assertEqual(len(handler.session.saved_predictions), 1)
        self.assertEqual(handler.session.saved_predictions[0].owners[3], "berserker/morgan")

    def test_card_select_stops_on_low_confidence_after_saving_evidence(self) -> None:
        handler = DummyCardSelectHandler(_make_prediction(low_confidence=True))

        with self.assertRaises(RuntimeError):
            handler.handle()

        self.assertEqual(len(handler.session.saved_predictions), 1)
        self.assertEqual(len(handler.session.saved_rgb_frames), 1)
        self.assertEqual(handler.call_order, ["read_np", "read_cards"])

    def test_card_select_stops_on_joint_low_confidence_after_saving_evidence(self) -> None:
        handler = DummyCardSelectHandler(_make_joint_low_confidence_prediction())

        with self.assertRaisesRegex(RuntimeError, "整手联合分差不足"):
            handler.handle()

        self.assertEqual(len(handler.session.saved_predictions), 1)
        self.assertEqual(len(handler.session.saved_rgb_frames), 1)
        self.assertEqual(handler.call_order, ["read_np", "read_cards"])

    def test_smart_battle_card_select_prioritizes_support_noble_and_cards(self) -> None:
        prediction = CommandCardPrediction(
            frontline_servants=[
                "caster/zhuge_liang",
                "caster/merlin",
                "berserker/morgan",
            ],
            support_attacker="berserker/morgan",
            traces=[
                CommandCardTrace(
                    index=1,
                    owner="caster/zhuge_liang",
                    color="arts",
                    score=0.4,
                    margin=0.2,
                    support_badge=False,
                    low_confidence=False,
                    scores=[],
                ),
                CommandCardTrace(
                    index=2,
                    owner="caster/merlin",
                    color="arts",
                    score=0.4,
                    margin=0.2,
                    support_badge=False,
                    low_confidence=False,
                    scores=[],
                ),
                CommandCardTrace(
                    index=3,
                    owner="caster/zhuge_liang",
                    color="buster",
                    score=0.4,
                    margin=0.2,
                    support_badge=False,
                    low_confidence=False,
                    scores=[],
                ),
                CommandCardTrace(
                    index=4,
                    owner="berserker/morgan",
                    color="quick",
                    score=0.4,
                    margin=0.2,
                    support_badge=False,
                    low_confidence=False,
                    scores=[],
                ),
                CommandCardTrace(
                    index=5,
                    owner="berserker/morgan",
                    color="buster",
                    score=0.4,
                    margin=0.2,
                    support_badge=False,
                    low_confidence=False,
                    scores=[],
                ),
            ],
            min_score=0.07,
            min_margin=0.002,
            joint_score=0.4,
            joint_margin=0.1,
            joint_low_confidence=False,
        )
        handler = DummyCardSelectHandler(
            prediction,
            smart_battle_enabled=True,
        )
        np_statuses = [
            ServantNpStatus(1, "100", 100, 0.9, True, True),
            ServantNpStatus(2, "0", 0, 0.9, True, False),
            ServantNpStatus(3, "100", 100, 0.9, True, True),
        ]

        plan = CardSelectHandler.build_card_plan(
            handler,
            np_statuses,
            prediction.owners,
            prediction.cards,
        )

        self.assertEqual(
            plan,
            [
                {"type": "noble", "index": 3},
                {"type": "noble", "index": 1},
                {"type": "card", "index": 4},
            ],
        )

    def test_custom_sequence_card_select_defers_unready_noble_and_prefers_support_cards(
        self,
    ) -> None:
        handler = DummyCustomCardSelectHandler(
            nobles=[3],
            recognized_cards=[
                CommandCardInfo(index=1, owner="caster/zhuge_liang", color="arts"),
                CommandCardInfo(index=2, owner="caster/merlin", color="arts"),
                CommandCardInfo(index=3, owner="caster/zhuge_liang", color="arts"),
                CommandCardInfo(index=4, owner="berserker/morgan", color="quick"),
                CommandCardInfo(index=5, owner="caster/merlin", color="buster"),
            ],
            np_statuses=[
                ServantNpStatus(1, "10", 10, 0.9, False, True),
                ServantNpStatus(2, "20", 20, 0.9, False, True),
                ServantNpStatus(3, "80", 80, 0.9, False, True),
            ],
        )

        handler.handle()

        self.assertEqual(
            handler.executed_plan,
            [
                {"type": "card", "index": 4},
                {"type": "card", "index": 1},
                {"type": "card", "index": 2},
            ],
        )
        self.assertEqual(handler.session.pending_custom_nobles, [3])

    def test_custom_sequence_card_select_releases_deferred_noble_once_ready(self) -> None:
        handler = DummyCustomCardSelectHandler(
            nobles=[],
            pending_nobles=[3],
            recognized_cards=[
                CommandCardInfo(index=1, owner="caster/zhuge_liang", color="arts"),
                CommandCardInfo(index=2, owner="caster/merlin", color="arts"),
                CommandCardInfo(index=3, owner="caster/zhuge_liang", color="arts"),
                CommandCardInfo(index=4, owner="berserker/morgan", color="quick"),
                CommandCardInfo(index=5, owner="caster/merlin", color="buster"),
            ],
            np_statuses=[
                ServantNpStatus(1, "10", 10, 0.9, False, True),
                ServantNpStatus(2, "20", 20, 0.9, False, True),
                ServantNpStatus(3, "100", 100, 0.9, True, True),
            ],
        )

        handler.handle()

        self.assertEqual(
            handler.executed_plan,
            [
                {"type": "noble", "index": 3},
                {"type": "card", "index": 4},
                {"type": "card", "index": 1},
            ],
        )
        self.assertEqual(handler.session.pending_custom_nobles, [])

    def test_custom_sequence_card_select_stops_when_card_color_missing(self) -> None:
        handler = DummyCustomCardSelectHandler(
            colors=["arts", "arts", None, "quick", "buster"],
            np_statuses=[
                ServantNpStatus(1, "10", 10, 0.9, False, True),
                ServantNpStatus(2, "20", 20, 0.9, False, True),
                ServantNpStatus(3, "30", 30, 0.9, False, True),
            ],
        )

        with self.assertRaises(RuntimeError):
            handler.handle()

    def test_battle_result_clears_pending_custom_nobles(self) -> None:
        handler = DummyBattleResultHandler(stage=3)
        handler.session.pending_custom_nobles = [3]
        handler.session.recognizer.match.side_effect = (
            lambda template_path, screen: {
                "next.png": (321, 654),
            }.get(template_path)
        )

        handler.handle()

        self.assertEqual(handler.session.pending_custom_nobles, [])

    def test_loading_handler_waits_for_next_page_to_stabilize_after_tips_disappear(
        self,
    ) -> None:
        handler = DummyLoadingHandler()

        handler.handle()

        self.assertEqual(
            handler.waiter.template_disappear_calls,
            [
                {
                    "template_path": "tips-template",
                    "timeout": 60.0,
                    "poll_interval": 4.0,
                }
            ],
        )
        self.assertEqual(
            handler.waiter.stable_calls,
            [
                {
                    "region": None,
                    "stable_frames": 2,
                    "timeout": 3.0,
                    "poll_interval": 0.5,
                }
            ],
        )

    def test_unknown_handler_defers_fallback_until_second_unknown(self) -> None:
        session = DummyUnknownSession(click_result=True)
        handler = UnknownHandler(session, DummyWaiter())
        unknown = StateDetectionResult(
            state=GameState.UNKNOWN,
            screen_path="screen.png",
            elapsed=0.01,
            best_match_state=GameState.LOADING_TIPS,
            best_score=0.66,
            matched_template="tips.png",
            missing_templates=[],
        )

        handler.handle(unknown)

        session.adb.click_raw.assert_not_called()
        self.assertEqual(session.consecutive_unknown_count, 1)
        self.assertTrue(session.unknown_snapshot_saved)

        handler.handle(unknown)

        session.recognizer.match.assert_called()
        session.adb.click_raw.assert_called_once_with(321, 654)
        self.assertEqual(
            handler.waiter.calls,
            [("未知状态兜底：已点击左上角关闭", 0.5)],
        )
        self.assertEqual(session.consecutive_unknown_count, 0)
        self.assertFalse(session.unknown_snapshot_saved)


class WaiterStateEntryTest(unittest.TestCase):
    def test_confirm_state_entry_support_select_adds_buffer_and_stability_check(
        self,
    ) -> None:
        waiter = RecordingStateEntryWaiter()

        result = waiter.confirm_state_entry(GameState.SUPPORT_SELECT)

        self.assertTrue(result)
        self.assertEqual(
            waiter.calls,
            [("检测到助战选择界面，等待列表加载稳定", 2.0)],
        )
        self.assertEqual(
            waiter.stable_calls,
            [
                {
                    "region": GameCoordinates.SUPPORT_PORTRAIT_STRIP,
                    "stable_frames": 2,
                    "timeout": 3.0,
                    "poll_interval": 0.5,
                }
            ],
        )

    def test_confirm_state_entry_card_select_waits_for_card_region(self) -> None:
        waiter = RecordingStateEntryWaiter()

        result = waiter.confirm_state_entry(GameState.CARD_SELECT)

        self.assertTrue(result)
        self.assertEqual(waiter.calls, [])
        self.assertEqual(
            waiter.stable_calls,
            [
                {
                    "region": (77, 586, 1891, 927),
                    "stable_frames": 2,
                    "timeout": 1.5,
                    "poll_interval": 0.2,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
