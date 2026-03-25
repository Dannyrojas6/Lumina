"""统一管理截图输出路径和模板资源路径。"""

from dataclasses import dataclass, field

from core.game_state import GameState


@dataclass(frozen=True)
class ResourceCatalog:
    """集中维护当前项目使用的图片资源位置。"""

    image_dir: str = "test_image"
    screen_path: str = "assets/screenshots/screen.png"
    state_templates: dict[GameState, str] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "state_templates",
            {
                GameState.DIALOG: self.template("skip.png"),
                GameState.CARD_SELECT: self.template("fight_speed.png"),
                GameState.WAVE_START: self.template("fight_menu.png"),
                GameState.BATTLE_RESULT: self.template("fight_result.png"),
                GameState.MAIN_MENU: self.template("main_menu.png"),
            },
        )

    def template(self, filename: str) -> str:
        """返回模板图片的完整路径。"""
        return f"{self.image_dir}/{filename}"
