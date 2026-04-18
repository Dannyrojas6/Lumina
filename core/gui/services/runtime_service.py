"""GUI 运行页对主链装配层的调用封装。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from core.runtime.app import RuntimeAssembly, RuntimeEventCallbacks, build_runtime
from core.shared import BattleConfig, load_battle_config


def load_runtime_config(
    config_path: str | Path = "config/battle_config.yaml",
) -> BattleConfig:
    """读取当前主运行配置。"""
    return load_battle_config(str(config_path))


def build_runtime_assembly(
    *,
    config_path: str | Path = "config/battle_config.yaml",
    event_callbacks: RuntimeEventCallbacks | None = None,
    extra_log_handlers: Sequence[logging.Handler] | None = None,
) -> RuntimeAssembly:
    """为 GUI 组装一次主链运行依赖。"""
    return build_runtime(
        config_path=str(config_path),
        event_callbacks=event_callbacks,
        extra_log_handlers=extra_log_handlers,
    )
