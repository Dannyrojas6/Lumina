import logging

from core.adb_controller import AdbController
from core.config import load_battle_config
from core.image_recognizer import ImageRecognizer
from core.workflow import DailyAction


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def run() -> None:
    setup_logging()
    config = load_battle_config()
    adb_ctl = AdbController()
    recognizer = ImageRecognizer(threshold=config.match_threshold)
    daily_action = DailyAction(adb_ctl, recognizer, config)
    daily_action.run()
