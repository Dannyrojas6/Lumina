from pathlib import Path

from core.game_state import GameState
from core.image_recognizer import ImageRecognizer


class StateDetector:
    def __init__(
        self,
        recognizer: ImageRecognizer,
        screen_callback,
        image_dir: str = "test_image",
    ) -> None:
        self.recognizer = recognizer
        self.screen_callback = screen_callback
        self.image_dir = image_dir
        self.state_templates = {
            GameState.DIALOG: f"{self.image_dir}/skip.png",
            GameState.CARD_SELECT: f"{self.image_dir}/fight_speed.png",
            GameState.WAVE_START: f"{self.image_dir}/fight_menu.png",
            GameState.BATTLE_RESULT: f"{self.image_dir}/fight_result.png",
            GameState.MAIN_MENU: f"{self.image_dir}/main_menu.png",
        }

    def detect(self) -> tuple[GameState, str]:
        screen_path = self.screen_callback()
        for state, template_path in self.state_templates.items():
            if Path(template_path).exists() and self.recognizer.match(
                template_path, screen_path
            ):
                return state, screen_path
        return GameState.UNKNOWN, screen_path
