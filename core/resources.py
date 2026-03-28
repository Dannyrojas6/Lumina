"""统一管理截图输出路径和模板资源路径。"""

from dataclasses import dataclass, field
from pathlib import Path

from core.game_state import GameState


@dataclass(frozen=True)
class ResourceCatalog:
    """集中维护当前项目使用的图片资源位置。"""

    assets_dir: str = "assets"
    legacy_ui_dir: str = "assets/ui"
    screen_path: str = "assets/screenshots/screen.png"
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

    def _resolve_with_fallback(self, preferred: Path, legacy: Path) -> str:
        """在新旧目录间解析模板路径。"""
        if preferred.exists():
            return str(preferred)
        if legacy.exists():
            return str(legacy)
        return str(preferred)
