"""战斗配置加载与默认值定义。"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

import yaml


class SkillAction(TypedDict):
    """描述一次技能释放动作。"""

    type: Literal["servant", "master"]
    skill: int
    target: int | None


@dataclass
class SupportRecognitionConfig:
    """描述助战头像识别的阈值与调试配置。"""

    backend: str = "template"
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

    backend: str = "rapidocr"
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
    phase: str = "buff"


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
    fail_mode: Literal["conservative"] = "conservative"
    sample_mode: bool = False

    @classmethod
    def from_yaml(cls, data: Any) -> "SmartBattleConfig":
        """从 YAML 节点加载智能战斗配置。"""
        if isinstance(data, cls):
            return data
        raw = data or {}
        if not isinstance(raw, dict):
            raise TypeError("smart_battle must be a mapping")
        return cls(
            enabled=bool(raw.get("enabled", False)),
            frontline=_parse_frontline(raw.get("frontline", [])),
            wave_plan=_parse_wave_plan(raw.get("wave_plan", [])),
            fail_mode=_parse_fail_mode(raw.get("fail_mode", "conservative")),
            sample_mode=bool(raw.get("sample_mode", False)),
        )


@dataclass
class BattleConfig:
    """控制单次刷本流程的配置项。"""

    loop_count: int = 10
    skill_sequence: list = field(default_factory=list)
    match_threshold: float = 0.75
    save_debug_screenshots: bool = False
    log_level: str = "INFO"
    skill_interval: float = 1.5
    skill_pre_skip_delay: float = 0.5
    master_skill_open_delay: float = 0.4
    quest_slot: int = 1
    support: SupportConfig = field(default_factory=SupportConfig)
    ocr: BattleOcrConfig = field(default_factory=BattleOcrConfig)
    smart_battle: SmartBattleConfig = field(default_factory=SmartBattleConfig)

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
                recognition=_parse_support_recognition(
                    support_data.get("recognition", {})
                ),
            )
        ocr_data = data.get("ocr", {})
        if isinstance(ocr_data, BattleOcrConfig):
            ocr = ocr_data
        else:
            ocr = BattleOcrConfig(
                backend=str(ocr_data.get("backend", "rapidocr")),
                min_confidence=float(ocr_data.get("min_confidence", 0.8)),
                np_ready_value=int(ocr_data.get("np_ready_value", 100)),
                retry_once_on_low_confidence=bool(
                    ocr_data.get("retry_once_on_low_confidence", True)
                ),
                save_ocr_crops=bool(ocr_data.get("save_ocr_crops", False)),
            )
        smart_battle = SmartBattleConfig.from_yaml(data.get("smart_battle", {}))
        data["support"] = support
        data["ocr"] = ocr
        data["smart_battle"] = smart_battle
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
                recognition=SupportRecognitionConfig(),
            ),
            ocr=BattleOcrConfig(),
            smart_battle=SmartBattleConfig(),
            skill_pre_skip_delay=0.5,
            master_skill_open_delay=0.4,
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

    def smart_battle_config(self) -> dict[str, Any]:
        """返回扁平化的智能战斗配置，便于后续决策层读取。"""
        return asdict(self.smart_battle)


def load_battle_config(config_path: str = "config/battle_config.yaml") -> BattleConfig:
    """优先加载磁盘配置，缺失时退回默认配置。"""
    if Path(config_path).exists():
        return BattleConfig.from_yaml(config_path)
    return BattleConfig.default()


def _parse_frontline(data: Any) -> list[SmartBattleFrontlineSlot]:
    """解析 frontline 配置。"""
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("smart_battle.frontline must be a list")
    slots: list[SmartBattleFrontlineSlot] = []
    seen_slots: set[int] = set()
    for item in data:
        if isinstance(item, SmartBattleFrontlineSlot):
            slot = item
        else:
            if not isinstance(item, dict):
                raise TypeError("smart_battle.frontline items must be mappings")
            for key in ("slot", "servant", "role", "is_support"):
                if key not in item:
                    raise ValueError(f"smart_battle.frontline item requires {key}")
            slot_value = int(item.get("slot"))
            if slot_value < 1 or slot_value > 3:
                raise ValueError("smart_battle.frontline.slot must be within 1..3")
            if slot_value in seen_slots:
                raise ValueError("smart_battle.frontline.slot must be unique")
            role = _parse_frontline_role(item.get("role", "attacker"))
            slot = SmartBattleFrontlineSlot(
                slot=slot_value,
                servant=str(item.get("servant", "")),
                role=role,
                is_support=bool(item.get("is_support", False)),
            )
        if slot.slot < 1 or slot.slot > 3:
            raise ValueError("smart_battle.frontline.slot must be within 1..3")
        if slot.slot in seen_slots:
            raise ValueError("smart_battle.frontline.slot must be unique")
        seen_slots.add(slot.slot)
        slots.append(slot)
    slots.sort(key=lambda item: item.slot)
    return slots


def _parse_wave_plan(data: Any) -> list[SmartBattleWavePlan]:
    """解析 wave_plan 配置，兼容键值表与列表两种写法。"""
    if data is None:
        return []
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = [{"wave": key, "actions": value} for key, value in data.items()]
    else:
        raise TypeError("smart_battle.wave_plan must be a list or mapping")

    plans: list[SmartBattleWavePlan] = []
    for item in entries:
        if isinstance(item, SmartBattleWavePlan):
            plans.append(item)
            continue
        if not isinstance(item, dict):
            raise TypeError("smart_battle.wave_plan items must be mappings")
        if isinstance(data, list):
            for key in ("wave", "actions"):
                if key not in item:
                    raise ValueError(f"smart_battle.wave_plan item requires {key}")
        wave_value = int(item.get("wave"))
        actions_data = item.get("actions", [])
        if isinstance(actions_data, dict):
            if "actions" not in actions_data:
                raise ValueError("smart_battle.wave_plan mapping items require actions")
            actions_data = actions_data.get("actions", [])
        if not isinstance(actions_data, list):
            raise TypeError("smart_battle.wave_plan.actions must be a list")
        plans.append(
            SmartBattleWavePlan(
                wave=wave_value,
                actions=[_parse_wave_action(action) for action in actions_data],
            )
        )
    plans.sort(key=lambda item: item.wave)
    return plans


def _parse_wave_action(data: Any) -> SmartBattleAction:
    """解析单个波次动作。"""
    if isinstance(data, SmartBattleAction):
        return data
    if not isinstance(data, dict):
        raise TypeError("smart_battle.wave_plan action must be a mapping")
    if "actor" not in data:
        raise ValueError("smart_battle.wave_plan action requires actor")
    if "skill" not in data:
        raise ValueError("smart_battle.wave_plan action requires skill")
    condition_tags = data.get("condition_tags", [])
    if isinstance(condition_tags, str):
        condition_tags = [condition_tags]
    if not isinstance(condition_tags, list):
        raise TypeError("smart_battle.wave_plan action condition_tags must be a list")
    return SmartBattleAction(
        actor=data["actor"],
        skill=int(data["skill"]),
        condition_tags=[str(tag) for tag in condition_tags],
        phase=str(data.get("phase", "buff")),
    )


def _parse_frontline_role(value: Any) -> Literal["attacker", "support", "hybrid"]:
    """解析 frontline 角色类型。"""
    role = str(value).lower()
    if role not in {"attacker", "support", "hybrid"}:
        raise ValueError("smart_battle.frontline.role must be attacker/support/hybrid")
    return role  # type: ignore[return-value]


def _parse_fail_mode(value: Any) -> Literal["conservative"]:
    """解析 fail_mode。"""
    mode = str(value).lower()
    if mode != "conservative":
        raise ValueError("smart_battle.fail_mode only supports conservative")
    return "conservative"


def _parse_support_recognition(data: Any) -> SupportRecognitionConfig:
    """解析助战头像识别配置。"""
    if isinstance(data, SupportRecognitionConfig):
        return data
    raw = data or {}
    if not isinstance(raw, dict):
        raise TypeError("support.recognition must be a mapping")
    return SupportRecognitionConfig(
        backend=str(raw.get("backend", "template")),
        min_slot_score=float(raw.get("min_slot_score", 0.78)),
        min_slot_margin=float(raw.get("min_slot_margin", 0.004)),
        confirm_delay=float(raw.get("confirm_delay", 0.25)),
        save_debug_mismatches=bool(raw.get("save_debug_mismatches", True)),
        max_debug_images=int(raw.get("max_debug_images", 12)),
    )
