"""主流程编排层，负责状态机驱动和高层业务步骤。"""

import logging
import time
from typing import Callable, Optional

import cv2
import numpy as np

from core.adb_controller import AdbController
from core.battle_actions import BattleAction
from core.config import BattleConfig
from core.coordinates import GameCoordinates
from core.game_state import GameState
from core.image_recognizer import ImageRecognizer
from core.resources import ResourceCatalog
from core.state_detector import StateDetector

log = logging.getLogger("core.workflow")


class DailyAction:
    """管理一次自动刷本流程的高层状态机。"""

    def __init__(
        self,
        adb_ctl: AdbController,
        recognizer: ImageRecognizer,
        config: BattleConfig,
        resources: ResourceCatalog,
    ) -> None:
        self.adb = adb_ctl
        self.recognizer = recognizer
        self.battle = BattleAction(adb_ctl)
        self.config = config
        self.resources = resources
        self.state = GameState.UNKNOWN
        self.state_detector = StateDetector(
            recognizer=recognizer,
            screen_callback=self._refresh_screen,
            resources=resources,
            screen_array_callback=self._get_latest_screen_image,
        )
        self.handlers: dict[GameState, Callable[[], None]] = {
            GameState.DIALOG: self.handle_dialog,
            GameState.WAVE_START: self.handle_wave_start,
            GameState.CARD_SELECT: self.handle_card_select,
            GameState.BATTLE_RESULT: self.handle_battle_result,
        }
        self._latest_screen_image: Optional[np.ndarray] = None
        self._current_wave = 0
        self._loop_done = 0

    def _refresh_screen(self) -> str:
        """更新当前截图文件并返回其路径。"""
        save_path = self.resources.screen_path if self.config.save_debug_screenshots else None
        image = self.adb.screenshot_array(save_path)
        self._latest_screen_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        return self.resources.screen_path

    def _get_latest_screen_image(self) -> np.ndarray:
        """返回最近一次刷新的灰度截图。"""
        if self._latest_screen_image is None:
            self._refresh_screen()
        return self._latest_screen_image

    def handle_dialog(self) -> None:
        """处理剧情跳过和确认弹窗。"""
        pos = self.recognizer.match(
            self.resources.template("skip.png"),
            self._get_latest_screen_image(),
        )
        if pos:
            self.adb.click_raw(*pos)
            time.sleep(0.2)
            self._refresh_screen()
            yes_pos = self.recognizer.match(
                self.resources.template("yes.png"),
                self._get_latest_screen_image(),
            )
            if yes_pos:
                self.adb.click_raw(*yes_pos)
                time.sleep(0.2)
            log.info("跳过对话")

    def handle_wave_start(self) -> None:
        """波次开始后按配置释放技能并进入攻击流程。"""
        self._current_wave += 1
        log.info(f"===== 第 {self._current_wave} 波 =====")

        skills_this_wave = [
            step["skills"]
            for step in self.config.skill_sequence
            if step["wave"] == self._current_wave
        ]
        if skills_this_wave:
            for skill_num in skills_this_wave[0]:
                self.battle.use_servant_skill(skill_num)
                time.sleep(0.5)

        self.battle.attack()

    def handle_card_select(self) -> None:
        """进入选卡界面后按默认策略出卡。"""
        self.battle.select_cards([1, 2, 3])
        time.sleep(1.0)

    def handle_battle_result(self) -> None:
        """处理结算界面并累计已完成次数。"""
        self._loop_done += 1
        self._current_wave = 0
        self.adb.click(*GameCoordinates.RESULT_CONTINUE)
        time.sleep(2)
        self.adb.click(*GameCoordinates.RESULT_CONTINUE)
        time.sleep(2)
        self.adb.click(*GameCoordinates.RESULT_NEXT)
        time.sleep(2)
        log.info(f"战斗结束，已完成 {self._loop_done} 次")

    def run(self) -> None:
        """循环识别界面状态，并分派给对应处理器。"""
        log.info("脚本启动，进入主循环")
        max_loops = self.config.loop_count
        while max_loops < 0 or self._loop_done < max_loops:
            self.state, _ = self.state_detector.detect()
            log.debug(f"当前状态：{self.state.name}")

            if self.state == GameState.MAIN_MENU:
                log.info("检测到主界面，流程结束")
                break
            handler = self.handlers.get(self.state)
            if handler is None:
                log.info("状态未知，等待1s后重试")
                time.sleep(1.0)
                continue
            handler()
