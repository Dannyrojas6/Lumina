from core.workflow import build_command_card_plan


def test_build_command_card_plan_uses_servant_priority_after_nobles():
    card_owners = {
        1: "caster/altria_caster",
        2: "berserker/morgan",
        3: "caster/zhuge_liang",
        4: "berserker/morgan",
        5: "caster/altria_caster",
    }

    plan = build_command_card_plan(
        noble_indices=[3],
        card_owners=card_owners,
        servant_priority=[
            "berserker/morgan",
            "caster/zhuge_liang",
            "caster/altria_caster",
        ],
    )

    assert plan == [
        {"type": "noble", "index": 3},
        {"type": "card", "index": 2},
        {"type": "card", "index": 4},
    ]


def test_build_command_card_plan_falls_back_left_to_right_for_unknown_cards():
    plan = build_command_card_plan(
        noble_indices=[],
        card_owners={
            1: None,
            2: "caster/zhuge_liang",
            3: None,
            4: "berserker/morgan",
            5: None,
        },
        servant_priority=["berserker/morgan", "caster/zhuge_liang"],
    )

    assert plan == [
        {"type": "card", "index": 4},
        {"type": "card", "index": 2},
        {"type": "card", "index": 1},
    ]
