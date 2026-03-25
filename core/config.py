"""战斗配置加载与默认值定义。"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class BattleConfig:
    """控制单次刷本流程的配置项。"""

    total_waves: int = 3
    loop_count: int = 10
    skill_sequence: list[dict] = field(default_factory=list)
    match_threshold: float = 0.75
    save_debug_screenshots: bool = False

    @classmethod
    def from_yaml(cls, path: str) -> "BattleConfig":
        """从 YAML 文件加载配置。"""
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return cls(**data)

    @classmethod
    def default(cls) -> "BattleConfig":
        """提供最小可用的默认战斗配置。"""
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
    """优先加载磁盘配置，缺失时退回默认配置。"""
    if Path(config_path).exists():
        return BattleConfig.from_yaml(config_path)
    return BattleConfig.default()
