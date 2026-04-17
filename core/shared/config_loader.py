"""战斗配置加载与解析。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from core.shared.config_models import (
    BattleConfig,
    BattleOcrConfig,
    CustomSequenceAction,
    CustomSequenceBattleConfig,
    CustomTurnPlan,
    DeviceConfig,
    SmartBattleConfig,
    SmartBattleFrontlineSlot,
    SupportConfig,
    SupportRecognitionConfig,
)


def battle_config_from_yaml(path: str) -> BattleConfig:
    """从 YAML 文件加载配置。"""
    config_path = Path(path)
    with open(config_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    battle_mode = parse_battle_mode(data.get("battle_mode", "main"))
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
    custom_sequence_battle = parse_custom_sequence_battle(
        data.get("custom_sequence_battle", {}),
        config_path=config_path,
        load_turns=(battle_mode == "custom_sequence"),
    )
    data["device"] = device
    data["support"] = support
    data["ocr"] = ocr
    data["smart_battle"] = smart_battle
    data["custom_sequence_battle"] = custom_sequence_battle
    data["battle_mode"] = battle_mode
    data["continue_battle"] = bool(data.get("continue_battle", True))
    data["default_skill_target"] = parse_default_skill_target(
        data.get("default_skill_target", 3)
    )
    return BattleConfig(**data)


def default_battle_config() -> BattleConfig:
    """提供最小可用的默认战斗配置。"""
    return BattleConfig(
        loop_count=10,
        battle_mode="main",
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
        custom_sequence_battle=CustomSequenceBattleConfig(),
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


def custom_sequence_directory_for_config(config_path: Path) -> Path:
    """返回当前 battle_config 对应的自定义操作序列目录。"""
    return config_path.parent / "custom_sequences"


def resolve_custom_sequence_path(config_path: Path, sequence_name: str) -> Path:
    """解析自定义操作序列文件路径，并限制在配置目录下。"""
    normalized_name = str(sequence_name).strip()
    if not normalized_name:
        raise ValueError("custom_sequence_battle.sequence must not be empty")

    base_dir = custom_sequence_directory_for_config(config_path).resolve()
    resolved_path = (base_dir / normalized_name).resolve()
    if not resolved_path.is_relative_to(base_dir):
        raise ValueError("custom_sequence_battle.sequence must stay within config/custom_sequences")
    return resolved_path


def load_custom_sequence_turns_from_file(
    config_path: Path,
    sequence_name: str,
) -> list[CustomTurnPlan]:
    """从独立 YAML 文件加载自定义操作序列。"""
    sequence_path = resolve_custom_sequence_path(config_path, sequence_name)
    if not sequence_path.exists():
        raise FileNotFoundError(
            f"custom sequence file not found: {sequence_path}"
        )

    with open(sequence_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise TypeError("custom sequence file must be a mapping")

    turns = data.get("turns", [])
    if turns is None:
        turns = []
    if not isinstance(turns, list):
        raise TypeError("custom sequence file turns must be a list")
    return parse_custom_sequence_turns(turns)


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


def parse_battle_mode(data: Any) -> Literal["main", "custom_sequence"]:
    """解析顶层战斗模式。"""
    mode = str(data).strip().lower()
    if mode not in {"main", "custom_sequence"}:
        raise ValueError("battle_mode must be main or custom_sequence")
    return mode  # type: ignore[return-value]


def parse_custom_sequence_battle(
    data: Any,
    *,
    config_path: Path | None = None,
    load_turns: bool = True,
) -> CustomSequenceBattleConfig:
    """解析自定义操作序列战斗配置。"""
    if isinstance(data, CustomSequenceBattleConfig):
        return data
    raw = data or {}
    if not isinstance(raw, dict):
        raise TypeError("custom_sequence_battle must be a mapping")
    sequence = str(raw.get("sequence", "")).strip()
    turns = raw.get("turns", [])
    if turns is None:
        turns = []
    if sequence and turns:
        raise ValueError("custom_sequence_battle cannot define both sequence and turns")
    if sequence:
        if not load_turns:
            parsed_turns = []
        else:
            if config_path is None:
                raise ValueError("custom_sequence_battle.sequence requires config_path")
            parsed_turns = load_custom_sequence_turns_from_file(config_path, sequence)
    else:
        if not isinstance(turns, list):
            raise TypeError("custom_sequence_battle.turns must be a list")
        parsed_turns = parse_custom_sequence_turns(turns)
    return CustomSequenceBattleConfig(sequence=sequence, turns=parsed_turns)


def parse_custom_sequence_turns(data: list[Any]) -> list[CustomTurnPlan]:
    """解析自定义回合配置。"""
    turns: list[CustomTurnPlan] = []
    seen_turns: set[tuple[int, int]] = set()
    for item in data:
        if isinstance(item, CustomTurnPlan):
            turn_plan = item
        else:
            if not isinstance(item, dict):
                raise TypeError("custom_sequence_battle.turns items must be mappings")
            wave = int(item.get("wave", 0))
            turn = int(item.get("turn", 0))
            if wave < 1:
                raise ValueError("custom_sequence_battle.turns.wave must be >= 1")
            if turn < 1:
                raise ValueError("custom_sequence_battle.turns.turn must be >= 1")
            actions_data = item.get("actions", [])
            nobles_data = item.get("nobles", [])
            if actions_data is None:
                actions_data = []
            if nobles_data is None:
                nobles_data = []
            if not isinstance(actions_data, list):
                raise TypeError("custom_sequence_battle.turns.actions must be a list")
            if not isinstance(nobles_data, list):
                raise TypeError("custom_sequence_battle.turns.nobles must be a list")
            turn_plan = CustomTurnPlan(
                wave=wave,
                turn=turn,
                actions=[parse_custom_sequence_action(action) for action in actions_data],
                nobles=parse_custom_sequence_nobles(nobles_data),
            )
        if turn_plan.turn_key in seen_turns:
            raise ValueError("custom_sequence_battle.turns contains duplicate wave+turn")
        seen_turns.add(turn_plan.turn_key)
        turns.append(turn_plan)
    turns.sort(key=lambda item: (item.wave, item.turn))
    return turns


def parse_custom_sequence_action(data: Any) -> CustomSequenceAction:
    """解析自定义战斗动作。"""
    if isinstance(data, CustomSequenceAction):
        return data
    if not isinstance(data, dict):
        raise TypeError("custom_sequence_battle.turns.actions items must be mappings")
    action_type = str(data.get("type", "")).strip().lower()
    if action_type == "enemy_target":
        return CustomSequenceAction(
            type="enemy_target",
            target=parse_optional_target(
                data.get("target"),
                field_name="enemy_target.target",
                allow_none=False,
            ),
        )
    if action_type == "servant_skill":
        actor = int(data.get("actor", 0))
        skill = int(data.get("skill", 0))
        if actor < 1 or actor > 3:
            raise ValueError("custom_sequence servant_skill.actor must be within 1..3")
        if skill < 1 or skill > 3:
            raise ValueError("custom_sequence servant_skill.skill must be within 1..3")
        return CustomSequenceAction(
            type="servant_skill",
            actor=actor,
            skill=skill,
            target=parse_optional_target(
                data.get("target"),
                field_name="servant_skill.target",
            ),
        )
    if action_type == "master_skill":
        skill = int(data.get("skill", 0))
        if skill < 1 or skill > 3:
            raise ValueError("custom_sequence master_skill.skill must be within 1..3")
        if skill == 3:
            raise ValueError("custom_sequence master_skill.skill=3 当前未支持，请先不要配置换人")
        return CustomSequenceAction(
            type="master_skill",
            skill=skill,
            target=parse_optional_target(
                data.get("target"),
                field_name="master_skill.target",
            ),
        )
    raise ValueError(
        "custom_sequence action.type must be enemy_target, servant_skill, or master_skill"
    )


def parse_custom_sequence_nobles(data: list[Any]) -> list[int]:
    """解析当前回合要释放的宝具顺序。"""
    nobles: list[int] = []
    seen: set[int] = set()
    for item in data:
        value = int(item)
        if value < 1 or value > 3:
            raise ValueError("custom_sequence nobles must be within 1..3")
        if value in seen:
            raise ValueError("custom_sequence nobles must not contain duplicates")
        seen.add(value)
        nobles.append(value)
    return nobles


def parse_optional_target(
    data: Any,
    *,
    field_name: str,
    allow_none: bool = True,
) -> int | None:
    """解析目标位。"""
    if data is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} must be within 1..3")
    value = int(data)
    if value < 1 or value > 3:
        raise ValueError(f"{field_name} must be within 1..3")
    return value


def _ensure_no_deprecated_smart_battle_fields(raw: dict[str, Any]) -> None:
    """拒绝当前已废弃但仍可能出现在旧 YAML 里的字段。"""
    if "fail_mode" in raw:
        raise ValueError("smart_battle.fail_mode 已废弃，请删除该字段")
    if "wave_plan" in raw:
        raise ValueError("smart_battle.wave_plan 已废弃，请删除该字段")
