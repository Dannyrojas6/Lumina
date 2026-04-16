"""战斗配置加载与解析。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from core.shared.config_models import (
    BattleConfig,
    BattleOcrConfig,
    DeviceConfig,
    SmartBattleAction,
    SmartBattleConfig,
    SmartBattleFrontlineSlot,
    SmartBattleWavePlan,
    SupportConfig,
    SupportRecognitionConfig,
)


def battle_config_from_yaml(path: str) -> BattleConfig:
    """从 YAML 文件加载配置。"""
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    device_data = data.get("device", {})
    if isinstance(device_data, DeviceConfig):
        device = device_data
    else:
        device = DeviceConfig(
            profile=str(device_data.get("profile", "mumu_1920x1080")),
            serial=str(device_data.get("serial", "")),
            connect_targets=parse_connect_targets(
                device_data.get("connect_targets", ["127.0.0.1:7555"])
            ),
        )
    support_data = data.get("support", {})
    if isinstance(support_data, SupportConfig):
        support = support_data
    else:
        support = SupportConfig(
            class_name=str(support_data.get("class", "all")),
            servant=str(support_data.get("servant", "")),
            pick_index=int(support_data.get("pick_index", 1)),
            max_scroll_pages=int(support_data.get("max_scroll_pages", 3)),
            recognition=parse_support_recognition(
                support_data.get("recognition", {})
            ),
        )
    ocr_data = data.get("ocr", {})
    if isinstance(ocr_data, BattleOcrConfig):
        ocr = ocr_data
    else:
        ocr = BattleOcrConfig(
            min_confidence=float(ocr_data.get("min_confidence", 0.8)),
            np_ready_value=int(ocr_data.get("np_ready_value", 100)),
            retry_once_on_low_confidence=bool(
                ocr_data.get("retry_once_on_low_confidence", True)
            ),
            save_ocr_crops=bool(ocr_data.get("save_ocr_crops", False)),
        )
    smart_battle = parse_smart_battle_config(data.get("smart_battle", {}))
    data["device"] = device
    data["support"] = support
    data["ocr"] = ocr
    data["smart_battle"] = smart_battle
    data["continue_battle"] = bool(data.get("continue_battle", True))
    data["default_skill_target"] = parse_default_skill_target(
        data.get("default_skill_target", 3)
    )
    return BattleConfig(**data)


def default_battle_config() -> BattleConfig:
    """提供最小可用的默认战斗配置。"""
    return BattleConfig(
        loop_count=10,
        continue_battle=True,
        default_skill_target=3,
        log_level="INFO",
        quest_slot=1,
        device=DeviceConfig(),
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


def load_battle_config(config_path: str = "config/battle_config.yaml") -> BattleConfig:
    """优先加载磁盘配置，缺失时退回默认配置。"""
    if Path(config_path).exists():
        return battle_config_from_yaml(config_path)
    return default_battle_config()


def parse_smart_battle_config(data: Any) -> SmartBattleConfig:
    """从 YAML 节点加载智能战斗配置。"""
    if isinstance(data, SmartBattleConfig):
        return data
    raw = data or {}
    if not isinstance(raw, dict):
        raise TypeError("smart_battle must be a mapping")
    _ensure_no_deprecated_smart_battle_fields(raw)
    return SmartBattleConfig(
        enabled=bool(raw.get("enabled", False)),
        frontline=parse_frontline(raw.get("frontline", [])),
        wave_plan=parse_wave_plan(raw.get("wave_plan", [])),
        command_card_priority=parse_command_card_priority(
            raw.get("command_card_priority", [])
        ),
    )


def parse_frontline(data: Any) -> list[SmartBattleFrontlineSlot]:
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
            role = parse_frontline_role(item.get("role", "attacker"))
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


def parse_wave_plan(data: Any) -> list[SmartBattleWavePlan]:
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
                actions=[parse_wave_action(action) for action in actions_data],
            )
        )
    plans.sort(key=lambda item: item.wave)
    return plans


def parse_wave_action(data: Any) -> SmartBattleAction:
    """解析单个波次动作。"""
    if isinstance(data, SmartBattleAction):
        return data
    if not isinstance(data, dict):
        raise TypeError("smart_battle.wave_plan action must be a mapping")
    if "actor" not in data:
        raise ValueError("smart_battle.wave_plan action requires actor")
    if "skill" not in data:
        raise ValueError("smart_battle.wave_plan action requires skill")
    if "phase" in data:
        raise ValueError("smart_battle.wave_plan.actions.phase 已废弃，请删除该字段")
    condition_tags = data.get("condition_tags", [])
    if isinstance(condition_tags, str):
        condition_tags = [condition_tags]
    if not isinstance(condition_tags, list):
        raise TypeError("smart_battle.wave_plan action condition_tags must be a list")
    return SmartBattleAction(
        actor=data["actor"],
        skill=int(data["skill"]),
        condition_tags=[str(tag) for tag in condition_tags],
    )


def parse_frontline_role(value: Any) -> Literal["attacker", "support", "hybrid"]:
    """解析 frontline 角色类型。"""
    role = str(value).lower()
    if role not in {"attacker", "support", "hybrid"}:
        raise ValueError("smart_battle.frontline.role must be attacker/support/hybrid")
    return role  # type: ignore[return-value]


def parse_support_recognition(data: Any) -> SupportRecognitionConfig:
    """解析助战头像识别配置。"""
    if isinstance(data, SupportRecognitionConfig):
        return data
    raw = data or {}
    if not isinstance(raw, dict):
        raise TypeError("support.recognition must be a mapping")
    return SupportRecognitionConfig(
        min_slot_score=float(raw.get("min_slot_score", 0.78)),
        min_slot_margin=float(raw.get("min_slot_margin", 0.004)),
        confirm_delay=float(raw.get("confirm_delay", 0.25)),
        save_debug_mismatches=bool(raw.get("save_debug_mismatches", True)),
        max_debug_images=int(raw.get("max_debug_images", 12)),
    )


def parse_command_card_priority(data: Any) -> list[str]:
    """解析普通指令卡的从者优先顺序。"""
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("smart_battle.command_card_priority must be a list")
    return [
        str(item).replace("\\", "/").strip().strip("/")
        for item in data
        if str(item).strip()
    ]


def parse_connect_targets(data: Any) -> list[str]:
    """解析启动前自动连接的 adb 地址列表。"""
    if data is None:
        return []
    if not isinstance(data, list):
        raise TypeError("device.connect_targets must be a list")
    return [str(item).strip() for item in data if str(item).strip()]


def parse_default_skill_target(data: Any) -> int:
    """解析技能释放后默认目标位。"""
    target = int(data)
    if target < 1 or target > 3:
        raise ValueError("default_skill_target must be within 1..3")
    return target


def _ensure_no_deprecated_smart_battle_fields(raw: dict[str, Any]) -> None:
    """拒绝当前已废弃但仍可能出现在旧 YAML 里的字段。"""
    if "fail_mode" in raw:
        raise ValueError("smart_battle.fail_mode 已废弃，请删除该字段")
