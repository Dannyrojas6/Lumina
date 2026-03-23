from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class BattleConfig:
    total_waves: int = 3
    loop_count: int = 10
    skill_sequence: list[dict] = field(default_factory=list)
    match_threshold: float = 0.75

    @classmethod
    def from_yaml(cls, path: str) -> "BattleConfig":
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return cls(**data)

    @classmethod
    def default(cls) -> "BattleConfig":
        return cls(
            total_waves=3,
            loop_count=10,
            skill_sequence=[
                {"wave": 1, "skills": [1, 2, 3]},
                {"wave": 2, "skills": [4, 5, 6]},
                {"wave": 3, "skills": [7, 8, 9]},
            ],
        )


def load_battle_config(config_path: str = "config/battle_config.yaml") -> BattleConfig:
    if Path(config_path).exists():
        return BattleConfig.from_yaml(config_path)
    return BattleConfig.default()
