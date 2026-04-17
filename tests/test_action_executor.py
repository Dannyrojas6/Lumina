import unittest
from unittest.mock import Mock, patch

from core.battle_runtime.action_executor import BattleAction


class BattleActionTimingTest(unittest.TestCase):
    @patch("core.battle_runtime.action_executor.time.sleep")
    def test_uses_explicit_action_timing_values(
        self,
        sleep_mock,
    ) -> None:
        adb = Mock()
        action = BattleAction(
            adb,
            skill_interval=1.6,
            skill_pre_skip_delay=0.55,
            master_skill_open_delay=0.45,
            attack_button_delay=0.7,
            card_select_delay=0.2,
            target_select_delay=0.15,
        )

        action.attack()
        action.select_cards([1, 2, 3])
        action.select_noble_card(2)
        action.select_servant_target(3)
        action.select_enemy_target(2)

        self.assertEqual(
            [call.args[0] for call in sleep_mock.call_args_list],
            [0.7, 0.2, 0.2, 0.2, 0.2, 0.15, 0.15],
        )

    @patch("core.battle_runtime.action_executor.time.sleep")
    def test_select_enemy_target_logs_target_switch(
        self,
        sleep_mock,
    ) -> None:
        adb = Mock()
        action = BattleAction(adb, target_select_delay=0.2)

        with self.assertLogs("core.battle_actions", level="INFO") as captured:
            action.select_enemy_target(2)

        adb.click.assert_called_once()
        self.assertEqual(sleep_mock.call_args_list[0].args[0], 0.2)
        self.assertIn("已切换敌方目标=2", captured.output[-1])


if __name__ == "__main__":
    unittest.main()
