import logging
import time
from typing import Optional

from core.adb_controller import AdbController
from core.coordinates import GameCoordinates

log = logging.getLogger("core.battle_actions")


class BattleAction:
    def __init__(self, adb_ctl: AdbController) -> None:
        self.adb = adb_ctl

    def use_servant_skill(self, skill_num: int, target: Optional[int] = None) -> None:
        self.adb.click(*GameCoordinates.SERVANT_SKILLS[skill_num])
        time.sleep(0.5)

        if target is not None:
            self.adb.click(*GameCoordinates.TARGET_POSITIONS[target])
            time.sleep(0.3)

        self.adb.click(*GameCoordinates.SPEED_SKIP)
        log.info(f"技能 {skill_num} 释放完毕")

    def use_master_skill(self, skill_num: int, target: Optional[int] = None) -> None:
        self.adb.click_region(GameCoordinates.MASTER_SKILL)
        time.sleep(0.4)
        self.adb.click(*GameCoordinates.MASTER_SKILL_POSITIONS[skill_num])
        time.sleep(0.5)

        if target is not None:
            self.adb.click(*GameCoordinates.TARGET_POSITIONS[target])
            time.sleep(0.3)

        log.info(f"御主技能 {skill_num} 释放完毕")

    def attack(self) -> None:
        self.adb.click_region(GameCoordinates.ATTACK_BUTTON)
        time.sleep(0.5)
        log.info("进入攻击选卡")

    def select_cards(self, card_indices: list[int]) -> None:
        for idx in card_indices[:3]:
            self.adb.click(*GameCoordinates.CARD_POSITIONS[idx])
            time.sleep(0.3)
        log.info(f"已选卡：{card_indices[:3]}")

    def speed_skip(self) -> None:
        self.adb.click(*GameCoordinates.SPEED_SKIP)
