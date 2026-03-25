"""应用装配层，负责初始化依赖并启动主流程。"""

import logging

from core.adb_controller import AdbController
from core.config import load_battle_config
from core.image_recognizer import ImageRecognizer
from core.resources import ResourceCatalog
from core.workflow import DailyAction


def setup_logging() -> None:
    """初始化统一日志格式。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def run() -> None:
    """组装运行依赖并进入主循环。"""
    setup_logging()
    config = load_battle_config()
    resources = ResourceCatalog()
    adb_ctl = AdbController()
    recognizer = ImageRecognizer(threshold=config.match_threshold)
    daily_action = DailyAction(adb_ctl, recognizer, config, resources)
    daily_action.run()
