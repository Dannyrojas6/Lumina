"""普通指令卡样本真值清单。"""

from __future__ import annotations

import json
from pathlib import Path

from core.command_card_recognition.models import CommandCardSample

DEFAULT_SAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "replay" / "command_card_samples.json"
)


def load_command_card_samples(
    path: str | Path = DEFAULT_SAMPLE_PATH,
) -> list[CommandCardSample]:
    sample_path = Path(path)
    with sample_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise TypeError("command card sample catalog must be a list")

    samples: list[CommandCardSample] = []
    for item in data:
        if not isinstance(item, dict):
            raise TypeError("command card sample entry must be a mapping")
        owners = item.get("owners", [])
        frontline = item.get("frontline", [])
        if not isinstance(owners, list) or not isinstance(frontline, list):
            raise TypeError("command card sample owners/frontline must be lists")
        samples.append(
            CommandCardSample(
                image=str(item.get("image", "")),
                frontline=[str(servant) for servant in frontline],
                support_attacker=(
                    str(item["support_attacker"])
                    if item.get("support_attacker") is not None
                    else None
                ),
                owners=[
                    str(owner) if owner is not None else None
                    for owner in owners
                ],
                note=str(item.get("note", "")),
                occlusion_level=str(item.get("occlusion_level", "")),
                hard_negative_tags=[
                    str(tag) for tag in item.get("hard_negative_tags", [])
                ],
                source=str(item.get("source", "")),
            )
        )
    return samples
