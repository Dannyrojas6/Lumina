"""应用装配层，负责初始化依赖并启动主流程。"""

import logging

from core.adb_controller import AdbController
from core.config import BattleConfig, load_battle_config
from core.image_recognizer import ImageRecognizer
from core.resources import ResourceCatalog
from core.workflow import DailyAction


def setup_logging(config: BattleConfig) -> None:
    """初始化统一日志格式。"""
    level_name = config.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    if level_name not in logging.getLevelNamesMapping():
        logging.getLogger("core.app").warning(
            "未知日志级别 %s，已回退到 INFO",
            config.log_level,
        )


def run() -> None:
    """组装运行依赖并进入主循环。"""
    config = load_battle_config()
    setup_logging(config)
    resources = ResourceCatalog()
    adb_ctl = AdbController()
    recognizer = ImageRecognizer(threshold=config.match_threshold)
    daily_action = DailyAction(adb_ctl, recognizer, config, resources)
    daily_action.run()
