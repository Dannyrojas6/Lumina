"""显式页面处理器。"""

from core.runtime.handlers.battle_ready import BattleReadyHandler
from core.runtime.handlers.battle_result import BattleResultHandler
from core.runtime.handlers.card_select import CardSelectHandler
from core.runtime.handlers.dialog import DialogHandler
from core.runtime.handlers.loading import LoadingHandler
from core.runtime.handlers.main_menu import MainMenuHandler
from core.runtime.handlers.support_select import SupportSelectHandler
from core.runtime.handlers.team_confirm import TeamConfirmHandler
from core.runtime.handlers.unknown import UnknownHandler

__all__ = [
    "BattleReadyHandler",
    "BattleResultHandler",
    "CardSelectHandler",
    "DialogHandler",
    "LoadingHandler",
    "MainMenuHandler",
    "SupportSelectHandler",
    "TeamConfirmHandler",
    "UnknownHandler",
]
