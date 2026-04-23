import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


BASIC_INFO_FIELD_ORDER = (
    "id",
    "collectionNo",
    "name",
    "originalName",
    "ruby",
    "battleName",
    "originalBattleName",
    "classId",
    "className",
    "type",
    "flag",
    "flags",
    "rarity",
    "cost",
    "lvMax",
    "gender",
    "attribute",
    "cards",
)
BASIC_INFO_FIELDS = frozenset(BASIC_INFO_FIELD_ORDER)

ACTIVE_SKILL_FIELD_ORDER = (
    "num",
    "name",
    "coolDown",
    "effects",
)
ACTIVE_SKILL_FIELDS = frozenset(ACTIVE_SKILL_FIELD_ORDER)

NOBLE_PHANTASM_FIELD_ORDER = (
    "name",
    "ruby",
    "rank",
    "type",
    "card",
    "effects",
)
NOBLE_PHANTASM_FIELDS = frozenset(NOBLE_PHANTASM_FIELD_ORDER)

EXCLUDED_FIELD_ORDER = (
    "extraAssets",
    "relateQuestIds",
    "trialQuestIds",
    "growthCurve",
    "atkGrowth",
    "hpGrowth",
    "bondGrowth",
    "expGrowth",
    "expFeed",
    "bondGifts",
    "bondEquip",
    "bondEquips",
    "valentineEquip",
    "valentineScript",
    "ascensionImage",
    "ascensionMaterials",
    "skillMaterials",
    "appendSkillMaterials",
    "costumeMaterials",
    "coin",
    "script",
    "charaScripts",
    "battlePoints",
    "extraPassive",
    "hitsDistribution",
    "traits",
    "starAbsorb",
    "starGen",
    "instantDeathChance",
    "cardDetails",
    "atkBase",
    "atkMax",
    "hpBase",
    "hpMax",
    "classPassive",
    "appendPassive",
    "limits",
    "ascensionAdd",
    "traitAdd",
    "svtChange",
    "overwrites",
)
EXCLUDED_FIELDS = frozenset(EXCLUDED_FIELD_ORDER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a minimal battle-core export from a raw Atlas servant JSON.")
    parser.add_argument("source", type=Path, help="Raw Atlas servant JSON path.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. When omitted, the filtered JSON is printed to stdout.",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        help="Optional Markdown output path for human-readable servant data.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def classify_top_level_fields(payload: Mapping[str, Any]) -> dict[str, str]:
    classification: dict[str, str] = {}
    unknown_fields: list[str] = []

    for field_name in payload:
        if field_name in BASIC_INFO_FIELDS:
            classification[field_name] = "basic_info"
        elif field_name == "skills":
            classification[field_name] = "active_skills"
        elif field_name == "noblePhantasms":
            classification[field_name] = "noble_phantasms"
        elif field_name in EXCLUDED_FIELDS:
            classification[field_name] = "excluded"
        else:
            unknown_fields.append(field_name)

    if unknown_fields:
        unknown_text = ", ".join(sorted(unknown_fields))
        raise ValueError(f"unknown top-level servant fields: {unknown_text}")

    return classification


def _pick_fields(payload: Mapping[str, Any], field_order: tuple[str, ...]) -> dict[str, Any]:
    return {key: deepcopy(payload[key]) for key in field_order if key in payload}


def _filter_items(items: Any, field_order: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [_pick_fields(item, field_order) for item in items if isinstance(item, Mapping)]


def _compress_cool_down(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    compressed: list[int] = []
    for value in values:
        if value not in compressed:
            compressed.append(int(value))
    return compressed


def _effect(label: str, scale: str, values: list[str]) -> dict[str, Any]:
    return {"label": label, "scale": scale, "values": values}


def _format_tenths_percent(value: int) -> str:
    if value % 10 == 0:
        return f"{value // 10}%"
    return f"{value // 10}.{value % 10}%"


def _format_hundredths_percent(value: int) -> str:
    if value % 100 == 0:
        return f"{value // 100}%"
    whole = value // 100
    fraction = value % 100
    return f"{whole}.{fraction:02d}".rstrip("0").rstrip(".") + "%"


def _sval_values(function: Mapping[str, Any], key: str = "Value") -> list[int]:
    svals = function.get("svals")
    if not isinstance(svals, list):
        raise ValueError(f"missing svals for function: {function.get('funcType')}")
    values: list[int] = []
    for row in svals:
        if not isinstance(row, Mapping) or key not in row:
            raise ValueError(f"missing {key} in svals for function: {function.get('funcType')}")
        values.append(int(row[key]))
    return values


def _buff_types(function: Mapping[str, Any]) -> set[str]:
    buffs = function.get("buffs")
    if not isinstance(buffs, list):
        return set()
    return {str(buff.get("type")) for buff in buffs if isinstance(buff, Mapping)}


def _level_tenths_percent_effect(label: str, function: Mapping[str, Any]) -> dict[str, Any]:
    return _effect(
        label,
        "level",
        [_format_tenths_percent(value) for value in _sval_values(function)],
    )


def _level_hundredths_percent_effect(label: str, function: Mapping[str, Any]) -> dict[str, Any]:
    return _effect(
        label,
        "level",
        [_format_hundredths_percent(value) for value in _sval_values(function)],
    )


def _level_plain_effect(label: str, function: Mapping[str, Any]) -> dict[str, Any]:
    return _effect(label, "level", [str(value) for value in _sval_values(function)])


def _morgan_turn_end_down_values(function: Mapping[str, Any]) -> list[str]:
    values = _sval_values(function, key="Value2")
    return [f"{9 + value}%" if value < 10 else "20%" for value in values]


def _active_skill_effects(skill: Mapping[str, Any]) -> list[dict[str, Any]]:
    skill_num = int(skill.get("num", 0))
    functions = skill.get("functions")
    if not isinstance(functions, list):
        return []

    effects: list[dict[str, Any]] = []
    for function_index, function in enumerate(functions, start=1):
        if not isinstance(function, Mapping):
            continue
        func_type = function.get("funcType")
        func_target_type = function.get("funcTargetType")
        buff_types = _buff_types(function)

        if func_type == "hastenNpturn":
            continue
        if skill_num == 3 and func_type == "addStateShort" and "upCriticalrate" in buff_types:
            continue
        if func_type == "gainNp" and func_target_type == "self":
            effects.append(_level_hundredths_percent_effect("自身 NP 增加", function))
            continue
        if func_type == "gainNp" and func_target_type == "ptOne":
            effects.append(_level_hundredths_percent_effect("己方单体 NP 增加", function))
            continue
        if func_type == "gainStar":
            effects.append(_level_plain_effect("获得暴击星", function))
            continue
        if "upAtk" in buff_types:
            effects.append(_level_tenths_percent_effect("己方全体攻击力提升", function))
            continue
        if "downDefence" in buff_types:
            effects.append(_level_tenths_percent_effect("敌方全体防御力下降", function))
            continue
        if "upDropnp" in buff_types:
            effects.append(_level_tenths_percent_effect("己方全体 NP 获得量提升", function))
            continue
        if "guts" in buff_types:
            effects.append(_level_plain_effect("毅力回复", function))
            continue
        if "upStarweight" in buff_types:
            effects.append(_level_tenths_percent_effect("暴击星集中度提升", function))
            continue
        if "upCriticaldamage" in buff_types:
            effects.append(_level_tenths_percent_effect("暴击威力提升", function))
            continue
        if "selfturnendFunction" in buff_types and function_index == 5:
            values = _morgan_turn_end_down_values(function)
            effects.append(_effect("每回合敌方全体攻击力下降", "level", values))
            effects.append(_effect("暴击发生率下降", "level", values))
            continue
        if "selfturnendFunction" in buff_types and function_index == 6:
            continue

        raise ValueError(
            f"unsupported active skill effect: skill={skill.get('name')} "
            f"function={function_index} funcType={func_type} buffs={sorted(buff_types)}"
        )

    return effects


def _build_active_skill(skill: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "num": deepcopy(skill.get("num")),
        "name": deepcopy(skill.get("name")),
        "coolDown": deepcopy(skill.get("coolDown", [])),
        "effects": _active_skill_effects(skill),
    }


def _oc_sval_groups(function: Mapping[str, Any]) -> list[list[Mapping[str, Any]]]:
    groups: list[list[Mapping[str, Any]]] = []
    for key in ("svals", "svals2", "svals3", "svals4", "svals5"):
        value = function.get(key)
        if not isinstance(value, list):
            raise ValueError(f"missing {key} for noble phantasm function: {function.get('funcType')}")
        groups.append(value)
    return groups


def _noble_phantasm_effects(noble_phantasm: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = noble_phantasm.get("functions")
    if not isinstance(functions, list):
        return []

    effects: list[dict[str, Any]] = []
    for function_index, function in enumerate(functions, start=1):
        if not isinstance(function, Mapping):
            continue
        func_type = function.get("funcType")
        buff_types = _buff_types(function)

        if "upDamage" in buff_types:
            value = _sval_values(function)[0]
            effects.append(_effect("对圆桌骑士或妖精特攻状态", "fixed", [_format_tenths_percent(value)]))
            continue
        if func_type == "damageNpIndividual":
            effects.append(
                _effect(
                    "宝具倍率",
                    "npLevel",
                    [_format_tenths_percent(value) for value in _sval_values(function)],
                )
            )
            correction_values = []
            for group in _oc_sval_groups(function):
                first = group[0]
                if not isinstance(first, Mapping) or "Correction" not in first:
                    raise ValueError("missing Correction for noble phantasm overcharge effect")
                correction_values.append(_format_tenths_percent(int(first["Correction"])))
            effects.append(_effect("对拥有人之力敌人特攻", "overCharge", correction_values))
            continue
        if "reduceHp" in buff_types:
            effects.append(_effect("诅咒", "fixed", [str(_sval_values(function)[0])]))
            continue
        if "upChagetd" in buff_types:
            effects.append(_effect("己方全体宝具 OC 上升状态", "none", ["Ø"]))
            continue

        raise ValueError(
            f"unsupported noble phantasm effect: noble_phantasm={noble_phantasm.get('name')} "
            f"function={function_index} funcType={func_type} buffs={sorted(buff_types)}"
        )

    return effects


def _build_noble_phantasm(noble_phantasm: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": deepcopy(noble_phantasm.get("name")),
        "ruby": deepcopy(noble_phantasm.get("ruby")),
        "rank": deepcopy(noble_phantasm.get("rank")),
        "type": deepcopy(noble_phantasm.get("type")),
        "card": deepcopy(noble_phantasm.get("card")),
        "effects": _noble_phantasm_effects(noble_phantasm),
    }


def build_servant_battle_core(payload: Mapping[str, Any]) -> dict[str, Any]:
    classify_top_level_fields(payload)
    noble_phantasms = [
        _build_noble_phantasm(item)
        for item in payload.get("noblePhantasms", [])
        if isinstance(item, Mapping)
    ]
    if len(noble_phantasms) != 1:
        raise ValueError(f"expected exactly one noble phantasm, got {len(noble_phantasms)}")

    return {
        "basicInfo": _pick_fields(payload, BASIC_INFO_FIELD_ORDER),
        "activeSkills": [
            _build_active_skill(item)
            for item in payload.get("skills", [])
            if isinstance(item, Mapping)
        ],
        "noblePhantasm": noble_phantasms[0],
    }


def _markdown_table_row(values: list[Any]) -> str:
    return "| " + " | ".join(str(value) for value in values) + " |"


def _join_values(values: list[str]) -> str:
    return " / ".join(values)


def render_servant_battle_core_markdown(
    payload: Mapping[str, Any],
    *,
    source_path: str,
    json_path: str,
) -> str:
    basic_info = payload["basicInfo"]
    active_skills = payload["activeSkills"]
    noble_phantasm = payload["noblePhantasm"]

    lines: list[str] = []
    lines.append("## 基本信息")
    lines.append("")
    lines.append("| 字段 | 当前值 |")
    lines.append("| --- | --- |")
    for key, value in basic_info.items():
        if isinstance(value, list):
            display_value = json.dumps(value, ensure_ascii=False)
        else:
            display_value = value
        lines.append(_markdown_table_row([f"`{key}`", display_value]))
    lines.append("")
    lines.append("## 主动技能")
    lines.append("")

    for skill in active_skills:
        lines.append(f"### 技能 {skill['num']}：{skill['name']}")
        lines.append("")
        cooldown = _compress_cool_down(skill["coolDown"])
        lines.append(f"- `coolDown`：{_join_values([str(value) for value in cooldown])}")
        lines.append("")
        lines.append("| 效果 | 刻度 | 数值 |")
        lines.append("| --- | --- | --- |")
        for effect in skill["effects"]:
            lines.append(
                _markdown_table_row(
                    [effect["label"], effect["scale"], _join_values(effect["values"])]
                )
            )
        lines.append("")

    lines.append(f"### 宝具：{noble_phantasm['name']}")
    lines.append("")
    lines.append(f"- `ruby`：{noble_phantasm['ruby']}")
    lines.append(f"- `rank`：{noble_phantasm['rank']}")
    lines.append(f"- `type`：{noble_phantasm['type']}")
    lines.append(f"- `card`：{noble_phantasm['card']}")
    lines.append("")
    lines.append("| 效果 | 刻度 | 数值 |")
    lines.append("| --- | --- | --- |")
    for effect in noble_phantasm["effects"]:
        values_text = _join_values(effect["values"])
        if values_text == "Ø":
            values_text = "`Ø`"
        lines.append(_markdown_table_row([effect["label"], effect["scale"], values_text]))

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = load_json(args.source)
    filtered = build_servant_battle_core(payload)
    if args.markdown_output is not None:
        json_path = str(args.output) if args.output is not None else "<stdout>"
        save_text(
            args.markdown_output,
            render_servant_battle_core_markdown(
                filtered,
                source_path=str(args.source),
                json_path=json_path,
            ),
        )
    if args.output is not None:
        save_json(args.output, filtered)
        return 0

    json.dump(filtered, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
