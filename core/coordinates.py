from typing import Final


class GameCoordinates:
    SERVANT_SKILLS: Final[dict[int, tuple[int, int]]] = {
        1: (110, 880),
        2: (243, 880),
        3: (376, 880),
        4: (585, 880),
        5: (718, 880),
        6: (850, 880),
        7: (1060, 880),
        8: (1200, 880),
        9: (1324, 880),
    }

    SERVANT_SKILL_REGIONS: Final[dict[str, tuple[int, int, int, int]]] = {
        "s1_1": (58, 812, 162, 921),
        "s1_2": (191, 816, 292, 920),
        "s1_3": (322, 810, 427, 922),
        "s2_1": (532, 811, 640, 922),
        "s2_2": (665, 811, 773, 923),
        "s2_3": (800, 810, 904, 923),
        "s3_1": (1011, 812, 1116, 923),
        "s3_2": (1144, 812, 1249, 923),
        "s3_3": (1277, 812, 1382, 923),
    }

    SKILL_SELECT_SERVANT: Final[tuple[int, int, int, int]] = (849, 262, 1077, 314)
    ATTACK_BUTTON: Final[tuple[int, int, int, int]] = (1600, 800, 1806, 1013)
    FIGHT_MENU: Final[tuple[int, int, int, int]] = (1700, 220, 1882, 389)
    MASTER_SKILL: Final[tuple[int, int, int, int]] = (1699, 379, 1885, 557)
    SPEED_SKIP: Final[tuple[int, int]] = (1849, 651)
    RESULT_CONTINUE: Final[tuple[int, int]] = (960, 540)
    RESULT_NEXT: Final[tuple[int, int]] = (1677, 961)
    TARGET_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        1: (430, 600),
        2: (720, 600),
        3: (1010, 600),
    }
    MASTER_SKILL_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        1: (1580, 460),
        2: (1715, 460),
        3: (1850, 460),
    }
    CARD_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        1: (290, 650),
        2: (570, 650),
        3: (860, 650),
        4: (1140, 650),
        5: (1420, 650),
    }

    @staticmethod
    def region_center(region: tuple[int, int, int, int]) -> tuple[int, int]:
        x1, y1, x2, y2 = region
        return (x1 + x2) // 2, (y1 + y2) // 2
