import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import Mock

from core.runtime.handlers.main_menu import MainMenuHandler
from core.runtime.handlers.support_select import SupportSelectHandler
from core.shared.config_loader import load_battle_config
from core.shared.config_models import BattleConfig, SupportConfig, SupportRecognitionConfig


class _DummyWaiter:
    def __init__(self) -> None:
        self.confirm_calls: list[object] = []
        self.calls: list[tuple[str, float]] = []

    def confirm_state_entry(self, state):
        self.confirm_calls.append(state)
        return True

    def wait_seconds(self, reason: str, seconds: float) -> None:
        self.calls.append((reason, seconds))


class _DummyMainMenuSession:
    def __init__(self, quest_slot: int) -> None:
        self.config = SimpleNamespace(quest_slot=quest_slot)
        self.adb = Mock()


class _DummySupportSelectSession:
    def __init__(
        self,
        *,
        servant: str,
        pick_index: int = 1,
        allow_fallback_pick: bool = False,
        verifier_available: bool = True,
    ) -> None:
        self.config = SimpleNamespace(
            support=SupportConfig(
                class_name="berserker",
                servant=servant,
                pick_index=pick_index,
                max_scroll_pages=3,
                allow_fallback_pick=allow_fallback_pick,
                recognition=SupportRecognitionConfig(),
            )
        )
        self.adb = Mock()
        self.stop_requested = False
        self._verifier_available = verifier_available

    def get_support_verifier(self, servant_name: str):
        return object() if self._verifier_available and servant_name else None


class _OrchestratingSupportHandler(SupportSelectHandler):
    def __init__(
        self,
        *,
        servant: str = "berserker/morgan",
        allow_fallback_pick: bool = False,
        verifier_available: bool = True,
        search_results: list[bool] | None = None,
        refresh_result: bool = False,
    ) -> None:
        self.waiter = _DummyWaiter()
        self.session = _DummySupportSelectSession(
            servant=servant,
            allow_fallback_pick=allow_fallback_pick,
            verifier_available=verifier_available,
        )
        self._search_results = list(search_results or [])
        self.refresh_result = refresh_result
        self.search_calls: list[tuple[str, int]] = []
        self.refresh_calls = 0
        self.fallback_pick_index: int | None = None

    def _select_support_class(self, support_class: str) -> None:
        return None

    def _search_and_pick_support(self, servant_name: str, max_scroll_pages: int) -> bool:
        self.search_calls.append((servant_name, max_scroll_pages))
        if not self._search_results:
            return False
        return self._search_results.pop(0)

    def _refresh_support_list(self) -> bool:
        self.refresh_calls += 1
        return self.refresh_result

    def _fallback_pick_support(self, pick_index: int) -> None:
        self.fallback_pick_index = pick_index


class StrictRuntimeGuardTest(unittest.TestCase):
    def test_missing_main_config_fails_instead_of_loading_defaults(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"

            with self.assertRaisesRegex(FileNotFoundError, "battle_config.yaml"):
                load_battle_config(str(config_path))

    def test_support_allow_fallback_pick_defaults_to_false(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    support:
                      servant: berserker/morgan
                    """
                ),
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))

            self.assertFalse(config.support.allow_fallback_pick)

    def test_support_allow_fallback_pick_can_be_enabled_explicitly(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    support:
                      servant: berserker/morgan
                      allow_fallback_pick: true
                    """
                ),
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))

            self.assertTrue(config.support.allow_fallback_pick)

    def test_rejects_invalid_main_runtime_values_during_load(self) -> None:
        invalid_cases = [
            (
                "match_threshold",
                "match_threshold: 0",
                "match_threshold",
            ),
            (
                "quest_slot",
                "quest_slot: 9",
                "quest_slot",
            ),
            (
                "support.pick_index",
                "support:\n  pick_index: 0",
                "support.pick_index",
            ),
            (
                "support.max_scroll_pages",
                "support:\n  max_scroll_pages: 0",
                "support.max_scroll_pages",
            ),
            (
                "support.recognition.confirm_delay",
                "support:\n  recognition:\n    confirm_delay: -0.1",
                "support.recognition.confirm_delay",
            ),
            (
                "skill_interval",
                "skill_interval: -0.1",
                "skill_interval",
            ),
        ]

        for name, payload, message in invalid_cases:
            with self.subTest(name=name), TemporaryDirectory() as tmp_dir:
                config_path = Path(tmp_dir) / "battle_config.yaml"
                config_path.write_text(dedent(payload), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, message):
                    BattleConfig.from_yaml(str(config_path))

    def test_main_menu_rejects_invalid_quest_slot_instead_of_falling_back(self) -> None:
        handler = MainMenuHandler(
            _DummyMainMenuSession(quest_slot=9),  # type: ignore[arg-type]
            _DummyWaiter(),  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(RuntimeError, "关卡槽位"):
            handler.handle()

        handler.session.adb.click.assert_not_called()

    def test_support_select_stops_when_target_verifier_is_unavailable(self) -> None:
        handler = _OrchestratingSupportHandler(verifier_available=False)

        with self.assertRaisesRegex(RuntimeError, "核验器"):
            handler.handle()

        self.assertEqual(handler.search_calls, [])
        self.assertIsNone(handler.fallback_pick_index)

    def test_support_select_stops_when_target_not_found_and_fallback_disabled(self) -> None:
        handler = _OrchestratingSupportHandler(
            allow_fallback_pick=False,
            search_results=[False, False],
            refresh_result=True,
        )

        with self.assertRaisesRegex(RuntimeError, "未找到目标助战"):
            handler.handle()

        self.assertEqual(
            handler.search_calls,
            [("berserker/morgan", 3), ("berserker/morgan", 3)],
        )
        self.assertIsNone(handler.fallback_pick_index)

    def test_support_select_allows_single_fallback_when_enabled_explicitly(self) -> None:
        handler = _OrchestratingSupportHandler(
            allow_fallback_pick=True,
            search_results=[False, False],
            refresh_result=True,
        )

        handler.handle()

        self.assertEqual(handler.refresh_calls, 1)
        self.assertEqual(handler.fallback_pick_index, 1)


if __name__ == "__main__":
    unittest.main()
