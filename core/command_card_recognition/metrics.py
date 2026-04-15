"""普通指令卡识别评估统计。"""

from __future__ import annotations

from statistics import mean
from typing import Any

from core.command_card_recognition.models import CommandCardPrediction, CommandCardSample


def compute_metrics(
    samples_with_predictions: list[tuple[CommandCardSample, CommandCardPrediction]],
) -> dict[str, Any]:
    sample_count = len(samples_with_predictions)
    if sample_count == 0:
        return {
            "sample_count": 0,
            "card_accuracy": 0.0,
            "hand_accuracy": 0.0,
            "margin_mean": 0.0,
            "occlusion_levels": {},
            "hard_negative": {},
        }

    total_cards = 0
    correct_cards = 0
    correct_hands = 0
    margins: list[float] = []
    occlusion_groups: dict[str, list[bool]] = {}
    hard_negative_groups: dict[str, list[bool]] = {}

    for sample, prediction in samples_with_predictions:
        hand_correct = prediction.owners == sample.owners_by_index
        if hand_correct:
            correct_hands += 1
        occlusion_groups.setdefault(sample.occlusion_level, []).append(hand_correct)
        for tag in sample.hard_negative_tags:
            hard_negative_groups.setdefault(tag, []).append(hand_correct)

        for trace in prediction.traces:
            total_cards += 1
            expected_owner = sample.owners_by_index[trace.index]
            if trace.owner == expected_owner:
                correct_cards += 1
            margins.append(trace.margin)

    return {
        "sample_count": sample_count,
        "card_accuracy": correct_cards / total_cards if total_cards else 0.0,
        "hand_accuracy": correct_hands / sample_count,
        "margin_mean": mean(margins) if margins else 0.0,
        "occlusion_levels": {
            key: sum(values) / len(values)
            for key, values in sorted(occlusion_groups.items())
            if key
        },
        "hard_negative": {
            key: sum(values) / len(values)
            for key, values in sorted(hard_negative_groups.items())
            if key
        },
    }
