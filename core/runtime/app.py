"""应用装配层，负责初始化依赖并启动主流程。"""

from dataclasses import dataclass
import logging
from typing import Callable, Sequence

from core.device import AdbController, FIXED_1920X1080
from core.battle_runtime import (
    BattleAction,
    BattleSnapshotReader,
)
from core.perception import BattleOcrReader, ImageRecognizer, OcrEngine
from core.shared import BattleConfig, ResourceCatalog, load_battle_config
from core.runtime.engine import AutomationEngine
from core.runtime.session import RuntimeSession
from core.runtime.startup_check import validate_runtime_prerequisites
from core.shared.game_types import GameState


StateChangedCallback = Callable[[GameState], None]
ScreenUpdatedCallback = Callable[[object], None]


@dataclass(frozen=True)
class RuntimeEventCallbacks:
    """描述运行期对外抛出的 GUI 事件回调。"""

    on_state_changed: StateChangedCallback | None = None
    on_screen_rgb: ScreenUpdatedCallback | None = None


@dataclass(frozen=True)
class RuntimeAssembly:
    """描述一次主链运行所需的完整装配结果。"""

    config: BattleConfig
    resources: ResourceCatalog
    adb: AdbController
    session: RuntimeSession
    engine: AutomationEngine


def setup_logging(
    config: BattleConfig,
    *,
    force: bool = False,
    extra_handlers: Sequence[logging.Handler] | None = None,
) -> None:
    """初始化统一日志格式。"""
    level_name = config.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    handlers = None
    if extra_handlers:
        handlers = [logging.StreamHandler(), *extra_handlers]
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        force=force,
        handlers=handlers,
    )
    # 屏蔽 Pillow 的 PNG 解析调试噪音，保留项目自身 DEBUG 日志。
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)
    if level_name not in logging.getLevelNamesMapping():
        logging.getLogger("core.app").warning(
            "未知日志级别 %s，已回退到 INFO",
            config.log_level,
        )


def build_runtime(
    *,
    config_path: str = "config/battle_config.yaml",
    event_callbacks: RuntimeEventCallbacks | None = None,
    extra_log_handlers: Sequence[logging.Handler] | None = None,
) -> RuntimeAssembly:
    """组装主链运行所需依赖。"""
    config = load_battle_config(config_path)
    setup_logging(config, extra_handlers=extra_log_handlers)
    log = logging.getLogger("core.app")
    log.debug("开始初始化资源目录")
    resources = ResourceCatalog()
    log.debug("开始初始化 ADB 控制器")
    adb_ctl = AdbController(
        serial=config.device.serial or None,
        connect_targets=config.device.connect_targets,
        profile=FIXED_1920X1080,
    )
    validate_runtime_prerequisites(
        config,
        resources,
        FIXED_1920X1080,
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
    setup_logging(config, force=True, extra_handlers=extra_log_handlers)
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
            attack_button_delay=FIXED_1920X1080.attack_button_delay,
            card_select_delay=FIXED_1920X1080.card_select_delay,
            target_select_delay=FIXED_1920X1080.target_select_delay,
        ),
        config=config,
        resources=resources,
        battle_ocr=battle_ocr,
        battle_snapshot_reader=battle_snapshot_reader,
        on_state_changed=(
            None if event_callbacks is None else event_callbacks.on_state_changed
        ),
        on_screen_rgb_updated=(
            None if event_callbacks is None else event_callbacks.on_screen_rgb
        ),
    )
    engine = AutomationEngine(session)
    log.debug("主流程组装完成，准备进入主循环")
    return RuntimeAssembly(
        config=config,
        resources=resources,
        adb=adb_ctl,
        session=session,
        engine=engine,
    )


def run(config_path: str = "config/battle_config.yaml") -> None:
    """组装运行依赖并进入主循环。"""
    assembly = build_runtime(config_path=config_path)
    assembly.engine.run()
