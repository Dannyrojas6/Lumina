"""应用装配层，负责初始化依赖并启动主流程。"""

import logging

from core.device import AdbController, resolve_device_profile
from core.battle_runtime import (
    BattleAction,
    BattleSnapshotReader,
)
from core.perception import BattleOcrReader, ImageRecognizer, OcrEngine
from core.shared import BattleConfig, ResourceCatalog, load_battle_config
from core.runtime.engine import AutomationEngine
from core.runtime.session import RuntimeSession
from core.runtime.startup_check import validate_runtime_prerequisites


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
    device_profile = resolve_device_profile(config.device.profile)
    adb_ctl = AdbController(
        serial=config.device.serial or None,
        connect_targets=config.device.connect_targets,
        profile=device_profile,
    )
    validate_runtime_prerequisites(
        config,
        resources,
        device_profile,
        device_resolution=adb_ctl.resolution,
    )
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
    if config.battle_mode == "custom_sequence":
        battle_snapshot_reader = BattleSnapshotReader(
            battle_ocr=battle_ocr,
            debug_dir=resources.ocr_debug_dir,
        )
    log.debug("开始组装主流程")
    session = RuntimeSession(
        adb=adb_ctl,
        recognizer=recognizer,
        battle=BattleAction(
            adb_ctl,
            skill_interval=config.skill_interval,
            skill_pre_skip_delay=config.skill_pre_skip_delay,
            master_skill_open_delay=config.master_skill_open_delay,
            attack_button_delay=device_profile.attack_button_delay,
            card_select_delay=device_profile.card_select_delay,
            target_select_delay=device_profile.target_select_delay,
        ),
        config=config,
        resources=resources,
        battle_ocr=battle_ocr,
        battle_snapshot_reader=battle_snapshot_reader,
    )
    engine = AutomationEngine(session)
    log.debug("主流程组装完成，准备进入主循环")
    engine.run()
