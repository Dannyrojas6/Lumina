"""战斗配置加载与默认值定义。"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, TypedDict

import yaml


class SkillAction(TypedDict):
    """描述一次技能释放动作。"""

    type: Literal["servant", "master"]
    skill: int
    target: int | None


@dataclass
class SupportConfig:
    """描述助战选择阶段的基础配置。"""

    class_name: str = "all"
    servant: str = ""
    pick_index: int = 1
    max_scroll_pages: int = 3


@dataclass
class BattleConfig:
    """控制单次刷本流程的配置项。"""

    loop_count: int = 10
    skill_sequence: list = field(default_factory=list)
    match_threshold: float = 0.75
    save_debug_screenshots: bool = False
    log_level: str = "INFO"
    skill_interval: float = 1.5
    quest_slot: int = 1
    support: SupportConfig = field(default_factory=SupportConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "BattleConfig":
        """从 YAML 文件加载配置。"""
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        support_data = data.get("support", {})
        if isinstance(support_data, SupportConfig):
            support = support_data
        else:
            support = SupportConfig(
                class_name=str(support_data.get("class", "all")),
                servant=str(support_data.get("servant", "")),
                pick_index=int(support_data.get("pick_index", 1)),
                max_scroll_pages=int(support_data.get("max_scroll_pages", 3)),
            )
        data["support"] = support
        return cls(**data)

    @classmethod
    def default(cls) -> "BattleConfig":
        """提供最小可用的默认战斗配置。"""
        return cls(
            loop_count=10,
            log_level="INFO",
            quest_slot=1,
            support=SupportConfig(
                class_name="all",
                servant="",
                pick_index=1,
                max_scroll_pages=3,
            ),
            skill_sequence=[
                1,
                2,
                3,
                4,
                5,
                6,
                {"type": "master", "skill": 1},
                {"type": "master", "skill": 2},
                {"type": "master", "skill": 3},
            ],
        )

    def battle_actions(self) -> list[SkillAction]:
        """返回当前战斗要执行的一次性技能动作序列。"""
        actions: list[SkillAction] = []
        for item in self.skill_sequence:
            if isinstance(item, int):
                actions.append({"type": "servant", "skill": item, "target": None})
                continue
            if isinstance(item, dict):
                if "type" in item and "skill" in item:
                    actions.append(
                        {
                            "type": str(item["type"]),
                            "skill": int(item["skill"]),
                            "target": (
                                int(item["target"])
                                if item.get("target") is not None
                                else None
                            ),
                        }
                    )
                    continue
                value = item.get("skills", [])
                if isinstance(value, list):
                    for skill in value:
                        actions.append(
                            {"type": "servant", "skill": int(skill), "target": None}
                        )
        return actions

    def support_config(self) -> dict[str, int | str]:
        """返回扁平化的助战配置，便于流程层读取。"""
        return asdict(self.support)


def load_battle_config(config_path: str = "config/battle_config.yaml") -> BattleConfig:
    """优先加载磁盘配置，缺失时退回默认配置。"""
    if Path(config_path).exists():
        return BattleConfig.from_yaml(config_path)
    return BattleConfig.default()
