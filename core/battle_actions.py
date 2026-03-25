"""战斗原子操作层，只封装单步点击行为。"""

import logging
import time
from typing import Optional

from core.adb_controller import AdbController
from core.coordinates import GameCoordinates

log = logging.getLogger("core.battle_actions")


class BattleAction:
    """提供技能、攻击和选卡等低层战斗动作。"""

    def __init__(self, adb_ctl: AdbController) -> None:
        self.adb = adb_ctl

    def use_servant_skill(self, skill_num: int, target: Optional[int] = None) -> None:
        """释放指定从者技能，可选带目标。"""
        self.adb.click(*GameCoordinates.SERVANT_SKILLS[skill_num])
        time.sleep(0.5)

        if target is not None:
            self.adb.click(*GameCoordinates.TARGET_POSITIONS[target])
            time.sleep(0.3)

        self.adb.click(*GameCoordinates.SPEED_SKIP)
        log.info(f"技能 {skill_num} 释放完毕")

    def use_master_skill(self, skill_num: int, target: Optional[int] = None) -> None:
        """释放御主技能，可选带目标。"""
        self.adb.click_region(GameCoordinates.MASTER_SKILL)
        time.sleep(0.4)
        self.adb.click(*GameCoordinates.MASTER_SKILL_POSITIONS[skill_num])
        time.sleep(0.5)

        if target is not None:
            self.adb.click(*GameCoordinates.TARGET_POSITIONS[target])
            time.sleep(0.3)

        log.info(f"御主技能 {skill_num} 释放完毕")

    def attack(self) -> None:
        """点击攻击按钮，进入选卡流程。"""
        self.adb.click_region(GameCoordinates.ATTACK_BUTTON)
        time.sleep(0.5)
        log.info("进入攻击选卡")

    def select_cards(self, card_indices: list[int]) -> None:
        """按传入顺序选择前三张卡。"""
        for idx in card_indices[:3]:
            self.adb.click(*GameCoordinates.CARD_POSITIONS[idx])
            time.sleep(0.3)
        log.info(f"已选卡：{card_indices[:3]}")

    def speed_skip(self) -> None:
        """点击战斗加速/跳过区域。"""
        self.adb.click(*GameCoordinates.SPEED_SKIP)
