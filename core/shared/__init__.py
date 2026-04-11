"""共享配置、资源、坐标与基础类型。"""

from core.shared.config_loader import load_battle_config
from core.shared.config_models import (
    BattleConfig,
    BattleOcrConfig,
    SkillAction,
    SmartBattleAction,
    SmartBattleConfig,
    SmartBattleFrontlineSlot,
    SmartBattleWavePlan,
    SupportConfig,
    SupportRecognitionConfig,
)
from core.shared.game_types import GameState
from core.shared.resource_catalog import ResourceCatalog
from core.shared.resource_manifest import (
    ServantManifest,
    ServantSkillManifest,
    SupportRecognitionManifest,
)
from core.shared.screen_coordinates import GameCoordinates

__all__ = [
    "BattleConfig",
    "BattleOcrConfig",
    "GameCoordinates",
    "GameState",
    "ResourceCatalog",
    "ServantManifest",
    "ServantSkillManifest",
    "SkillAction",
    "SmartBattleAction",
    "SmartBattleConfig",
    "SmartBattleFrontlineSlot",
    "SmartBattleWavePlan",
    "SupportConfig",
    "SupportRecognitionConfig",
    "SupportRecognitionManifest",
    "load_battle_config",
]
