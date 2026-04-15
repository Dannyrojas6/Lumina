"""统一的出卡计划构建。"""

from __future__ import annotations

from typing import Optional

from core.command_card_recognition import (
    CommandCardInfo,
    choose_best_card_chain,
)


def build_command_card_plan(
    *,
    noble_indices: list[int],
    card_owners: dict[int, str | None],
    servant_priority: list[str],
    cards: Optional[list[CommandCardInfo]] = None,
    support_attacker: str | None = None,
) -> list[dict[str, int]]:
    """按宝具优先和从者优先顺序构建统一出卡计划。"""
    plan: list[dict[str, int]] = [
        {"type": "noble", "index": servant_index} for servant_index in noble_indices[:3]
    ]
    if len(plan) >= 3:
        return plan[:3]

    remaining_cards = [index for index in (1, 2, 3, 4, 5)]
    used_cards: set[int] = set()
    normalized_priority = [
        str(item).replace("\\", "/").strip().strip("/")
        for item in servant_priority
        if str(item).strip()
    ]
    if cards:
        best_chain = choose_best_card_chain(
            cards=sorted(cards, key=lambda item: item.index),
            servant_priority=normalized_priority,
            support_attacker=support_attacker,
        )
        for card in best_chain:
            if len(plan) >= 3:
                return plan[:3]
            if card.index in used_cards:
                continue
            plan.append({"type": "card", "index": card.index})
            used_cards.add(card.index)

    for servant_name in normalized_priority:
        for card_index in remaining_cards:
            if len(plan) >= 3:
                return plan[:3]
            if card_index in used_cards:
                continue
            if card_owners.get(card_index) != servant_name:
                continue
            plan.append({"type": "card", "index": card_index})
            used_cards.add(card_index)

    for card_index in remaining_cards:
        if len(plan) >= 3:
            break
        if card_index in used_cards:
            continue
        plan.append({"type": "card", "index": card_index})
        used_cards.add(card_index)
    return plan[:3]
