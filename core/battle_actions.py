"""战斗原子操作层，只封装单步点击行为。"""

import logging
import time
from typing import Optional

from core.adb_controller import AdbController
from core.coordinates import GameCoordinates

log = logging.getLogger("core.battle_actions")


class BattleAction:
    """提供技能、攻击和选卡等低层战斗动作。"""

    def __init__(
        self,
        adb_ctl: AdbController,
        skill_interval: float = 1.5,
        skill_pre_skip_delay: float = 0.5,
        master_skill_open_delay: float = 0.4,
    ) -> None:
        self.adb = adb_ctl
        self.skill_interval = skill_interval
        self.skill_pre_skip_delay = skill_pre_skip_delay
        self.master_skill_open_delay = master_skill_open_delay

    def use_servant_skill(self, skill_num: int, target: Optional[int] = None) -> None:
        """释放指定从者技能，可选带目标。"""
        self.click_servant_skill(skill_num)
        if target is not None:
            self.select_servant_target(target)

        self.finish_servant_skill(skill_num, target=target)

    def use_master_skill(self, skill_num: int, target: Optional[int] = None) -> None:
        """释放御主技能，可选带目标。"""
        self.click_master_skill(skill_num)
        if target is not None:
            self.select_servant_target(target)

        self.finish_master_skill(skill_num, target=target)

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

    def select_noble_card(self, servant_index: int) -> None:
        """点击指定从者的宝具卡。"""
        self.adb.click(*GameCoordinates.NOBLE_CARD_POSITIONS[servant_index])
        time.sleep(0.3)

    def speed_skip(self) -> None:
        """点击战斗加速/跳过区域。"""
        self.adb.click(*GameCoordinates.SPEED_SKIP)

    def can_use_servant_skill(self, skill_num: int) -> bool:
        """预留从者技能可用性检查钩子。"""
        return True

    def can_use_master_skill(self, skill_num: int) -> bool:
        """预留御主技能可用性检查钩子。"""
        return True

    def click_servant_skill(self, skill_num: int) -> None:
        """点击从者技能按钮，进入技能后续处理。"""
        self.adb.click(*GameCoordinates.SERVANT_SKILLS[skill_num])
        time.sleep(self.skill_pre_skip_delay)

    def select_servant_target(self, target: int) -> None:
        """在技能目标选择界面中选择目标从者。"""
        self.adb.click(*GameCoordinates.TARGET_POSITIONS[target])
        time.sleep(0.3)

    def finish_servant_skill(
        self,
        skill_num: int,
        target: Optional[int] = None,
    ) -> None:
        """完成从者技能释放后的跳过与等待。"""
        self.adb.click(*GameCoordinates.SPEED_SKIP)
        time.sleep(self.skill_interval)
        if target is None:
            log.info(f"技能 {skill_num} 释放完毕")
            return
        log.info(f"技能 {skill_num} 释放完毕，默认目标={target}")

    def click_master_skill(self, skill_num: int) -> None:
        """打开御主技能栏并点击指定技能。"""
        self.adb.click_region(GameCoordinates.MASTER_SKILL)
        time.sleep(self.master_skill_open_delay)
        self.adb.click(*GameCoordinates.MASTER_SKILL_POSITIONS[skill_num])
        time.sleep(self.skill_pre_skip_delay)

    def finish_master_skill(
        self,
        skill_num: int,
        target: Optional[int] = None,
    ) -> None:
        """完成御主技能释放后的等待。"""
        self.adb.click(*GameCoordinates.SPEED_SKIP)
        time.sleep(self.skill_interval)
        if target is None:
            log.info(f"御主技能 {skill_num} 释放完毕")
            return
        log.info(f"御主技能 {skill_num} 释放完毕，默认目标={target}")
