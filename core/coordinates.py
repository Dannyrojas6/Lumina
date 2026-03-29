"""集中维护当前版本使用的游戏坐标常量。"""

from typing import Final


class GameCoordinates:
    """统一收口所有点击坐标和矩形区域。"""

    QUEST_SLOTS: Final[dict[int, tuple[int, int]]] = {
        1: (1400, 300),
        2: (1400, 550),
        3: (1400, 800),
    }
    SUPPORT_SCROLL_START: Final[tuple[int, int]] = (960, 450)
    SUPPORT_SCROLL_END: Final[tuple[int, int]] = (960, 50)
    BATTLE_INFO_REGION: Final[tuple[int, int, int, int]] = (1080, 0, 1910, 220)
    BATTLE_WAVE_REGION: Final[tuple[int, int, int, int]] = (1304, 13, 1434, 63)
    BATTLE_ENEMY_COUNT_REGION: Final[tuple[int, int, int, int]] = (1295, 67, 1474, 114)
    BATTLE_TURN_REGION: Final[tuple[int, int, int, int]] = (1297, 121, 1463, 166)

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
    BATTLE_SKILL_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: SERVANT_SKILL_REGIONS["s1_1"],
        2: SERVANT_SKILL_REGIONS["s1_2"],
        3: SERVANT_SKILL_REGIONS["s1_3"],
        4: SERVANT_SKILL_REGIONS["s2_1"],
        5: SERVANT_SKILL_REGIONS["s2_2"],
        6: SERVANT_SKILL_REGIONS["s2_3"],
        7: SERVANT_SKILL_REGIONS["s3_1"],
        8: SERVANT_SKILL_REGIONS["s3_2"],
        9: SERVANT_SKILL_REGIONS["s3_3"],
    }
    BATTLE_ENEMY_FALLBACK_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (40, 40, 720, 420),
        2: (660, 40, 1330, 420),
        3: (1290, 120, 1880, 500),
    }

    SKILL_SELECT_SERVANT: Final[tuple[int, int, int, int]] = (849, 262, 1077, 314)
    ATTACK_BUTTON: Final[tuple[int, int, int, int]] = (1600, 800, 1806, 1013)
    FIGHT_MENU: Final[tuple[int, int, int, int]] = (1700, 220, 1882, 389)
    MASTER_SKILL: Final[tuple[int, int, int, int]] = (1699, 379, 1885, 557)
    SPEED_SKIP: Final[tuple[int, int]] = (1849, 651)
    RESULT_CONTINUE: Final[tuple[int, int]] = (960, 540)
    RESULT_NEXT: Final[tuple[int, int]] = (1677, 961)
    TARGET_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        1: (500, 600),
        2: (1000, 600),
        3: (1500, 600),
    }
    MASTER_SKILL_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        1: (1360, 460),
        2: (1490, 460),
        3: (1620, 460),
    }
    SUPPORT_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        1: (200, 400),
        2: (200, 700),
        3: (200, 1000),
    }
    NOBLE_CARD_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        1: (600, 300),
        2: (950, 300),
        3: (1300, 300),
    }
    NP_TEXT_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (346, 986, 436, 1020),
        2: (817, 985, 913, 1020),
        3: (1288, 984, 1391, 1021),
    }
    SERVANT_HP_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (334, 931, 442, 968),
        2: (811, 930, 918, 968),
        3: (1290, 930, 1394, 968),
    }
    SERVANT_TRUE_NAME_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (247, 1039, 455, 1075),
        2: (722, 1040, 932, 1075),
        3: (1200, 1038, 1405, 1074),
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
        """返回矩形区域中心点。"""
        x1, y1, x2, y2 = region
        return (x1 + x2) // 2, (y1 + y2) // 2
