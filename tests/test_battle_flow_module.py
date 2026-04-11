import unittest

from core.battle_runtime.command_card_recognition import CommandCardInfo
from core.runtime.battle_flow import build_command_card_plan


class BattleFlowModuleTest(unittest.TestCase):
    def test_battle_flow_module_exposes_command_card_plan_builder(self) -> None:
        cards = [
            CommandCardInfo(index=1, owner="caster/merlin", color="buster"),
            CommandCardInfo(index=2, owner="caster/merlin", color="arts"),
            CommandCardInfo(index=3, owner="caster/merlin", color="quick"),
            CommandCardInfo(index=4, owner="berserker/morgan", color="buster"),
            CommandCardInfo(index=5, owner="berserker/morgan", color="buster"),
        ]

        plan = build_command_card_plan(
            noble_indices=[],
            card_owners={card.index: card.owner for card in cards},
            servant_priority=["berserker/morgan", "caster/merlin"],
            cards=cards,
            support_attacker="caster/merlin",
        )

        self.assertEqual(
            plan,
            [
                {"type": "card", "index": 1},
                {"type": "card", "index": 2},
                {"type": "card", "index": 3},
            ],
        )


if __name__ == "__main__":
    unittest.main()
