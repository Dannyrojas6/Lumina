"""智能战斗配置归一化。"""

from __future__ import annotations

from typing import Any

from core.battle_runtime.planner_models import (
    FrontlineServantConfig,
    ServantManifest,
    ServantSkillDefinition,
    WaveActionRule,
)


def normalize_frontline(frontline: list[Any]) -> list[FrontlineServantConfig]:
    """将配置层的 frontline 结构转换成判断层结构。"""
    normalized: list[FrontlineServantConfig] = []
    for item in frontline:
        normalized.append(
            FrontlineServantConfig(
                slot=int(_read_attr(item, "slot")),
                servant=str(_read_attr(item, "servant")),
                role=str(_read_attr(item, "role")),
                is_support=bool(_read_attr(item, "is_support", False)),
            )
        )
    return normalized


def normalize_wave_plan(wave_plan: list[Any]) -> dict[int, list[WaveActionRule]]:
    """将配置层的 wave_plan 结构转换成判断层结构。"""
    normalized: dict[int, list[WaveActionRule]] = {}
    for item in wave_plan:
        wave_index = int(_read_attr(item, "wave"))
        raw_actions = list(_read_attr(item, "actions", []))
        normalized[wave_index] = [
            WaveActionRule(
                actor=_read_attr(action, "actor"),
                skill=int(_read_attr(action, "skill")),
                condition_tags=[
                    str(tag) for tag in list(_read_attr(action, "condition_tags", []))
                ],
            )
            for action in raw_actions
        ]
    return normalized


def normalize_manifests(manifests: list[Any]) -> dict[str, ServantManifest]:
    """将资源层从者资料转换成判断层结构。"""
    normalized: dict[str, ServantManifest] = {}
    for item in manifests:
        if item is None:
            continue
        slug = str(_read_attr(item, "servant_name", _read_attr(item, "slug")))
        raw_skills = list(_read_attr(item, "skills", []))
        normalized[slug] = ServantManifest(
            slug=slug,
            display_name=str(_read_attr(item, "display_name", slug)),
            role_tags=[str(_read_attr(item, "role", ""))],
            skills=[
                ServantSkillDefinition(
                    skill_index=int(_read_attr(skill, "skill_index")),
                    effect_tags=[
                        str(tag) for tag in list(_read_attr(skill, "effect_tags", []))
                    ],
                    target_type=str(_read_attr(skill, "target_type", "team")),
                    priority_tags=[
                        str(tag)
                        for tag in list(_read_attr(skill, "priority_tags", []))
                    ],
                )
                for skill in raw_skills
            ],
        )
    return normalized


def _read_attr(item: Any, key: str, default: Any = None) -> Any:
    """兼容 dataclass、普通对象和 dict 的统一读值。"""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)
