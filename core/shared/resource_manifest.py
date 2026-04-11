"""从者资源结构与 manifest 解析。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SupportRecognitionManifest:
    """描述助战头像识别资源布局。"""

    source_dir: str = "atlas/faces"
    source_glob: str = "**/*.png"
    generated_dir: str = "support/generated"
    reference_bank: str = "support/generated/reference_bank.npz"
    reference_meta: str = "support/generated/reference_meta.json"


@dataclass(frozen=True)
class ServantSkillManifest:
    """描述从者单个技能的长期资料。"""

    skill_index: int
    effect_tags: list[str] = field(default_factory=list)
    target_type: str = ""
    priority_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ServantManifest:
    """描述从者资料文件的标准结构。"""

    servant_name: str
    display_name: str = ""
    class_name: str = ""
    support_recognition: SupportRecognitionManifest = field(
        default_factory=SupportRecognitionManifest
    )
    skills: list[ServantSkillManifest] = field(default_factory=list)


def parse_servant_skill(data: Any) -> ServantSkillManifest:
    """解析从者技能定义。"""
    if not isinstance(data, dict):
        raise TypeError("servant manifest skill must be a mapping")
    for key in ("skill_index", "effect_tags", "target_type", "priority_tags"):
        if key not in data:
            raise ValueError(f"servant manifest skill requires {key}")
    effect_tags = data.get("effect_tags", [])
    priority_tags = data.get("priority_tags", [])
    if isinstance(effect_tags, str):
        effect_tags = [effect_tags]
    if isinstance(priority_tags, str):
        priority_tags = [priority_tags]
    if not isinstance(effect_tags, list):
        raise TypeError("servant manifest skill effect_tags must be a list")
    if not isinstance(priority_tags, list):
        raise TypeError("servant manifest skill priority_tags must be a list")
    return ServantSkillManifest(
        skill_index=int(data.get("skill_index")),
        effect_tags=[str(tag) for tag in effect_tags],
        target_type=str(data.get("target_type", "")),
        priority_tags=[str(tag) for tag in priority_tags],
    )


def parse_support_recognition_manifest(data: Any) -> SupportRecognitionManifest:
    """解析助战头像识别资源定义。"""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise TypeError("support_recognition must be a mapping")
    return SupportRecognitionManifest(
        source_dir=str(data.get("source_dir", "atlas/faces")),
        source_glob=str(data.get("source_glob", "**/*.png")),
        generated_dir=str(data.get("generated_dir", "support/generated")),
        reference_bank=str(
            data.get("reference_bank", "support/generated/reference_bank.npz")
        ),
        reference_meta=str(
            data.get("reference_meta", "support/generated/reference_meta.json")
        ),
    )
