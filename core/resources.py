"""统一管理截图输出路径和模板资源路径。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.game_state import GameState


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
    role: str = ""
    support_template: str = "support/portrait.png"
    skills: list[ServantSkillManifest] = field(default_factory=list)


@dataclass(frozen=True)
class ResourceCatalog:
    """集中维护当前项目使用的图片资源位置。"""

    assets_dir: str = "assets"
    legacy_ui_dir: str = "assets/ui"
    screen_path: str = "assets/screenshots/screen.png"
    ocr_debug_dir: str = "assets/screenshots/ocr"
    state_templates: dict[GameState, str] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "state_templates",
            {
                GameState.SUPPORT_SELECT: self.state_template(
                    "support_select", "support_select.png"
                ),
                GameState.TEAM_CONFIRM: self.state_template(
                    "team_confirm", "team_confirm.png"
                ),
                GameState.LOADING_TIPS: self.state_template(
                    "loading_tips", "tips.png"
                ),
                GameState.DIALOG: self.state_template("dialog", "skip.png"),
                GameState.CARD_SELECT: self.state_template(
                    "card_select", "fight_speed.png"
                ),
                GameState.BATTLE_READY: self.state_template(
                    "battle_ready", "fight_menu.png"
                ),
                GameState.BATTLE_RESULT: self.state_template(
                    "battle_result", "fight_result.png"
                ),
                GameState.MAIN_MENU: self.state_template("main_menu", "main_menu.png"),
            },
        )

    def state_template(self, state_name: str, filename: str) -> str:
        """返回状态模板路径，优先走新目录结构，缺失时回退旧路径。"""
        return self._resolve_with_fallback(
            Path(self.assets_dir) / "states" / state_name / filename,
            Path(self.legacy_ui_dir) / filename,
        )

    def template(self, filename: str, category: str = "common") -> str:
        """返回通用 UI 模板路径，优先走新目录结构，缺失时回退旧路径。"""
        return self._resolve_with_fallback(
            Path(self.assets_dir) / "ui" / category / filename,
            Path(self.legacy_ui_dir) / filename,
        )

    def support_class_template(self, class_name: str) -> str:
        """返回助战职阶按钮模板路径。"""
        class_templates = {
            "all": "all_class.png",
            "berserker": "berserker.png",
        }
        filename = class_templates.get(class_name, class_templates["all"])
        return self.template(filename, category="support_select")

    def servant_template(
        self,
        servant_name: str,
        purpose: str = "support",
        filename: str = "portrait.png",
    ) -> str:
        """返回从者资料模板路径。"""
        return str(
            Path(self.assets_dir) / "servants" / servant_name / purpose / filename
        )

    def servant_manifest_path(self, servant_name: str) -> str:
        """返回从者资料文件路径。"""
        return str(Path(self.assets_dir) / "servants" / servant_name / "manifest.yaml")

    def load_servant_manifest(self, servant_name: str) -> ServantManifest | None:
        """加载单个从者资料。"""
        manifest_path = Path(self.servant_manifest_path(servant_name))
        if not manifest_path.exists():
            return None
        with manifest_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        if not isinstance(data, dict):
            raise TypeError("servant manifest must be a mapping")
        skills_data = data.get("skills", [])
        if not isinstance(skills_data, list):
            raise TypeError("servant manifest skills must be a list")
        skills = [_parse_servant_skill(item) for item in skills_data]
        return ServantManifest(
            servant_name=str(data.get("servant_name", servant_name)),
            display_name=str(data.get("display_name", "")),
            class_name=str(data.get("class_name", "")),
            role=str(data.get("role", "")),
            support_template=str(data.get("support_template", "support/portrait.png")),
            skills=skills,
        )

    def _resolve_with_fallback(self, preferred: Path, legacy: Path) -> str:
        """在新旧目录间解析模板路径。"""
        if preferred.exists():
            return str(preferred)
        if legacy.exists():
            return str(legacy)
        return str(preferred)


def _parse_servant_skill(data: Any) -> ServantSkillManifest:
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
