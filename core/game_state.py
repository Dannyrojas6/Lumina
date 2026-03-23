from enum import Enum, auto


class GameState(Enum):
    UNKNOWN = auto()
    MAIN_MENU = auto()
    IN_BATTLE = auto()
    WAVE_START = auto()
    CARD_SELECT = auto()
    BATTLE_RESULT = auto()
    DIALOG = auto()
