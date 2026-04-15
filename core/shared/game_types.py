"""状态机使用的游戏状态枚举。"""

from enum import Enum, auto


class GameState(Enum):
    """描述主流程当前识别到的界面状态。"""

    UNKNOWN = auto()
    MAIN_MENU = auto()
    SUPPORT_SELECT = auto()
    TEAM_CONFIRM = auto()
    LOADING_TIPS = auto()
    BATTLE_READY = auto()
    CARD_SELECT = auto()
    BATTLE_RESULT = auto()
    DIALOG = auto()
