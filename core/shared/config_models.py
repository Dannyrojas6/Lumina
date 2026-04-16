"""战斗配置数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


class SkillAction(TypedDict):
    """描述一次技能释放动作。"""

    type: Literal["servant", "master"]
    skill: int
    target: int | None


@dataclass
class DeviceConfig:
    """描述当前固定运行环境。"""

    profile: str = "mumu_1920x1080"
    serial: str = ""
    connect_targets: list[str] = field(default_factory=lambda: ["127.0.0.1:7555"])


@dataclass
class SupportRecognitionConfig:
    """描述助战头像识别的阈值与调试配置。"""

    min_slot_score: float = 0.78
    min_slot_margin: float = 0.004
    confirm_delay: float = 0.25
    save_debug_mismatches: bool = True
    max_debug_images: int = 12


@dataclass
class SupportConfig:
    """描述助战选择阶段的基础配置。"""

    class_name: str = "all"
    servant: str = ""
    pick_index: int = 1
    max_scroll_pages: int = 3
    recognition: SupportRecognitionConfig = field(
        default_factory=SupportRecognitionConfig
    )


@dataclass
class BattleOcrConfig:
    """描述 OCR 识别层的基础配置。"""

    min_confidence: float = 0.8
    np_ready_value: int = 100
    retry_once_on_low_confidence: bool = True
    save_ocr_crops: bool = False


@dataclass
class SmartBattleFrontlineSlot:
    """描述智能战斗前排单个槽位。"""

    slot: int
    servant: str = ""
    role: Literal["attacker", "support", "hybrid"] = "attacker"
    is_support: bool = False


@dataclass
class SmartBattleAction:
    """描述智能战斗中单个技能决策。"""

    actor: int | str
    skill: int
    condition_tags: list[str] = field(default_factory=list)


@dataclass
class SmartBattleWavePlan:
    """描述一波战斗要执行的动作列表。"""

    wave: int
    actions: list[SmartBattleAction] = field(default_factory=list)


@dataclass
class SmartBattleConfig:
    """描述智能战斗 v1 的策略配置。"""

    enabled: bool = False
    frontline: list[SmartBattleFrontlineSlot] = field(default_factory=list)
    wave_plan: list[SmartBattleWavePlan] = field(default_factory=list)
    command_card_priority: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, data: Any) -> "SmartBattleConfig":
        from core.shared.config_loader import parse_smart_battle_config

        return parse_smart_battle_config(data)


@dataclass
class BattleConfig:
    """控制单次刷本流程的配置项。"""

    loop_count: int = 10
    continue_battle: bool = True
    default_skill_target: int = 3
    skill_sequence: list = field(default_factory=list)
    match_threshold: float = 0.75
    save_debug_screenshots: bool = False
    log_level: str = "INFO"
    skill_interval: float = 1.5
    skill_pre_skip_delay: float = 0.5
    master_skill_open_delay: float = 0.4
    quest_slot: int = 1
    device: DeviceConfig = field(default_factory=DeviceConfig)
    support: SupportConfig = field(default_factory=SupportConfig)
    ocr: BattleOcrConfig = field(default_factory=BattleOcrConfig)
    smart_battle: SmartBattleConfig = field(default_factory=SmartBattleConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "BattleConfig":
        from core.shared.config_loader import battle_config_from_yaml

        return battle_config_from_yaml(path)

    @classmethod
    def default(cls) -> "BattleConfig":
        from core.shared.config_loader import default_battle_config

        return default_battle_config()

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
