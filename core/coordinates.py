"""集中维护当前版本使用的游戏坐标常量。"""

from typing import Final


def _skill_body_region(region: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """返回技能按钮主体区域，避开底部冷却提示。"""
    x1, y1, x2, y2 = region
    return (x1 + 6, y1 + 4, x2 - 6, y2 - 29)


def _skill_left_corner_region(
    region: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """返回技能左下角提示区域。"""
    x1, y1, x2, y2 = region
    return (x1, y2 - 39, min(x1 + 52, x2), y2)


def _skill_right_corner_region(
    region: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """返回技能右下角数字区域。"""
    x1, y1, x2, y2 = region
    return (max(x2 - 42, x1), y2 - 39, x2, y2)


class GameCoordinates:
    """统一收口所有点击坐标和矩形区域。"""

    QUEST_SLOTS: Final[dict[int, tuple[int, int]]] = {
        1: (1400, 300),
        2: (1400, 550),
        3: (1400, 800),
    }
    SUPPORT_SCROLL_START: Final[tuple[int, int]] = (960, 350)
    SUPPORT_SCROLL_END: Final[tuple[int, int]] = (960, 50)
    BATTLE_INFO_REGION: Final[tuple[int, int, int, int]] = (1080, 0, 1910, 220)
    BATTLE_WAVE_CURRENT_REGION: Final[tuple[int, int, int, int]] = (1285, 20, 1349, 56)
    BATTLE_WAVE_TOTAL_REGION: Final[tuple[int, int, int, int]] = (1368, 20, 1434, 58)
    BATTLE_ENEMY_COUNT_REGION: Final[tuple[int, int, int, int]] = (1396, 75, 1413, 108)
    BATTLE_TURN_REGION: Final[tuple[int, int, int, int]] = (1334, 126, 1379, 159)

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
    BATTLE_SKILL_BODY_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: _skill_body_region(BATTLE_SKILL_REGIONS[1]),
        2: _skill_body_region(BATTLE_SKILL_REGIONS[2]),
        3: _skill_body_region(BATTLE_SKILL_REGIONS[3]),
        4: _skill_body_region(BATTLE_SKILL_REGIONS[4]),
        5: _skill_body_region(BATTLE_SKILL_REGIONS[5]),
        6: _skill_body_region(BATTLE_SKILL_REGIONS[6]),
        7: _skill_body_region(BATTLE_SKILL_REGIONS[7]),
        8: _skill_body_region(BATTLE_SKILL_REGIONS[8]),
        9: _skill_body_region(BATTLE_SKILL_REGIONS[9]),
    }
    BATTLE_SKILL_LEFT_CORNER_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: _skill_left_corner_region(BATTLE_SKILL_REGIONS[1]),
        2: _skill_left_corner_region(BATTLE_SKILL_REGIONS[2]),
        3: _skill_left_corner_region(BATTLE_SKILL_REGIONS[3]),
        4: _skill_left_corner_region(BATTLE_SKILL_REGIONS[4]),
        5: _skill_left_corner_region(BATTLE_SKILL_REGIONS[5]),
        6: _skill_left_corner_region(BATTLE_SKILL_REGIONS[6]),
        7: _skill_left_corner_region(BATTLE_SKILL_REGIONS[7]),
        8: _skill_left_corner_region(BATTLE_SKILL_REGIONS[8]),
        9: _skill_left_corner_region(BATTLE_SKILL_REGIONS[9]),
    }
    BATTLE_SKILL_RIGHT_CORNER_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: _skill_right_corner_region(BATTLE_SKILL_REGIONS[1]),
        2: _skill_right_corner_region(BATTLE_SKILL_REGIONS[2]),
        3: _skill_right_corner_region(BATTLE_SKILL_REGIONS[3]),
        4: _skill_right_corner_region(BATTLE_SKILL_REGIONS[4]),
        5: _skill_right_corner_region(BATTLE_SKILL_REGIONS[5]),
        6: _skill_right_corner_region(BATTLE_SKILL_REGIONS[6]),
        7: _skill_right_corner_region(BATTLE_SKILL_REGIONS[7]),
        8: _skill_right_corner_region(BATTLE_SKILL_REGIONS[8]),
        9: _skill_right_corner_region(BATTLE_SKILL_REGIONS[9]),
    }
    BATTLE_ENEMY_FALLBACK_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (40, 40, 720, 420),
        2: (660, 40, 1330, 420),
        3: (1290, 120, 1880, 500),
    }
    ENEMY_HP_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (171, 63, 327, 94),
        2: (537, 64, 702, 93),
        3: (930, 65, 1077, 94),
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
        1: (195, 426),
        2: (197, 727),
        3: (196, 978),
    }
    SUPPORT_PORTRAIT_STRIP: Final[tuple[int, int, int, int]] = (68, 248, 324, 1079)
    SUPPORT_PORTRAIT_SLOT_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (74, 294, 317, 559),
        2: (74, 593, 320, 861),
        3: (70, 894, 322, 1063),
    }
    NOBLE_CARD_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        1: (600, 300),
        2: (950, 300),
        3: (1300, 300),
    }
    NP_TEXT_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (346, 987, 405, 1015),
        2: (822, 987, 880, 1015),
        3: (1302, 987, 1356, 1015),
    }
    SERVANT_HP_REGIONS: Final[dict[int, tuple[int, int, int, int] | None]] = {
        # 待校准，当前版本暂不使用。
        1: None,
        2: None,
        3: None,
    }
    SERVANT_TRUE_NAME_REGIONS: Final[dict[int, tuple[int, int, int, int] | None]] = {
        # 待校准，当前版本暂不使用。
        1: None,
        2: None,
        3: None,
    }
    COMMAND_CARD_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        1: (77, 586, 347, 927),
        2: (463, 586, 733, 927),
        3: (849, 586, 1119, 927),
        4: (1235, 586, 1505, 927),
        5: (1621, 586, 1891, 927),
    }
    CARD_POSITIONS: Final[dict[int, tuple[int, int]]] = {
        index: ((x1 + x2) // 2, (y1 + y2) // 2)
        for index, (x1, y1, x2, y2) in COMMAND_CARD_REGIONS.items()
    }
    COMMAND_CARD_FACE_REGIONS: Final[dict[int, tuple[int, int, int, int]]] = {
        index: (x1, y1, x2, y1 + ((y2 - y1) // 2))
        for index, (x1, y1, x2, y2) in COMMAND_CARD_REGIONS.items()
    }
    COMMAND_CARD_COLOR_ZONE_RATIOS: Final[tuple[float, float, float, float]] = (
        0.18,
        0.58,
        0.82,
        0.82,
    )

    @staticmethod
    def region_center(region: tuple[int, int, int, int]) -> tuple[int, int]:
        """返回矩形区域中心点。"""
        x1, y1, x2, y2 = region
        return (x1 + x2) // 2, (y1 + y2) // 2
