"""应用装配层，负责初始化依赖并启动主流程。"""

import logging

from core.battle_snapshot import BattleSnapshotReader
from core.battle_ocr import BattleOcrReader
from core.adb_controller import AdbController
from core.config import BattleConfig, load_battle_config
from core.image_recognizer import ImageRecognizer
from core.ocr_engine import OcrEngine
from core.resources import ResourceCatalog
from core.smart_battle import (
    SmartBattlePlanner,
    normalize_frontline,
    normalize_manifests,
    normalize_wave_plan,
)
from core.workflow import DailyAction


def setup_logging(config: BattleConfig, *, force: bool = False) -> None:
    """初始化统一日志格式。"""
    level_name = config.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        force=force,
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
    log = logging.getLogger("core.app")
    log.debug("开始初始化资源目录")
    resources = ResourceCatalog()
    log.debug("开始初始化 ADB 控制器")
    adb_ctl = AdbController()
    log.debug("开始初始化模板识别")
    recognizer = ImageRecognizer(threshold=config.match_threshold)
    log.debug("开始初始化 OCR 引擎")
    ocr_engine = OcrEngine(
        min_confidence=config.ocr.min_confidence,
        save_debug_crops=config.ocr.save_ocr_crops,
        debug_dir=resources.ocr_debug_dir,
    )
    # PaddleOCR 初始化后会改动全局日志级别，这里恢复项目自己的日志配置。
    setup_logging(config, force=True)
    log.debug("OCR 引擎初始化完成")
    battle_ocr = BattleOcrReader(ocr_engine=ocr_engine, config=config.ocr)
    battle_snapshot_reader = None
    smart_battle_planner = None
    if config.smart_battle.enabled:
        log.debug("开始初始化智能战斗配置")
        frontline = normalize_frontline(config.smart_battle.frontline)
        manifests = normalize_manifests(
            [
                resources.load_servant_manifest(slot.servant)
                for slot in config.smart_battle.frontline
            ]
        )
        battle_snapshot_reader = BattleSnapshotReader(
            battle_ocr=battle_ocr,
            debug_dir=resources.ocr_debug_dir,
        )
        smart_battle_planner = SmartBattlePlanner(
            frontline=frontline,
            manifests=manifests,
            wave_plan=normalize_wave_plan(config.smart_battle.wave_plan),
            fail_mode=config.smart_battle.fail_mode,
            np_ready_value=config.ocr.np_ready_value,
        )
        log.debug("智能战斗初始化完成")
    log.debug("开始组装主流程")
    daily_action = DailyAction(
        adb_ctl,
        recognizer,
        config,
        resources,
        battle_ocr,
        battle_snapshot_reader=battle_snapshot_reader,
        smart_battle_planner=smart_battle_planner,
    )
    log.debug("主流程组装完成，准备进入主循环")
    daily_action.run()
