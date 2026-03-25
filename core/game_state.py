"""状态机使用的游戏状态枚举。"""

from enum import Enum, auto


class GameState(Enum):
    """描述主流程当前识别到的界面状态。"""

    UNKNOWN = auto()
    MAIN_MENU = auto()
    IN_BATTLE = auto()
    WAVE_START = auto()
    CARD_SELECT = auto()
    BATTLE_RESULT = auto()
    DIALOG = auto()
