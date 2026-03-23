import logging
import time

from core.adb_controller import AdbController
from core.battle_actions import BattleAction
from core.config import BattleConfig
from core.coordinates import GameCoordinates
from core.game_state import GameState
from core.image_recognizer import ImageRecognizer
from core.state_detector import StateDetector

log = logging.getLogger("core.workflow")


class DailyAction:
    SCREEN_PATH = "screenshots/screen.png"
    IMAGE_DIR = "test_image"

    def __init__(
        self,
        adb_ctl: AdbController,
        recognizer: ImageRecognizer,
        config: BattleConfig,
    ) -> None:
        self.adb = adb_ctl
        self.recognizer = recognizer
        self.battle = BattleAction(adb_ctl)
        self.config = config
        self.state = GameState.UNKNOWN
        self.state_detector = StateDetector(
            recognizer=recognizer,
            screen_callback=self._refresh_screen,
            image_dir=self.IMAGE_DIR,
        )
        self._current_wave = 0
        self._loop_done = 0

    def _refresh_screen(self) -> str:
        return self.adb.screenshot(self.SCREEN_PATH)

    def handle_dialog(self) -> None:
        pos = self.recognizer.match(f"{self.IMAGE_DIR}/skip.png", self.SCREEN_PATH)
        if pos:
            self.adb.click_raw(*pos)
            time.sleep(0.2)
            self._refresh_screen()
            yes_pos = self.recognizer.match(
                f"{self.IMAGE_DIR}/yes.png", self.SCREEN_PATH
            )
            if yes_pos:
                self.adb.click_raw(*yes_pos)
                time.sleep(0.2)
            log.info("跳过对话")

    def handle_wave_start(self) -> None:
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
        self.battle.select_cards([1, 2, 3])
        time.sleep(1.0)

    def handle_battle_result(self) -> None:
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
        log.info("脚本启动，进入主循环")
        max_loops = self.config.loop_count
        while max_loops < 0 or self._loop_done < max_loops:
            self.state, _ = self.state_detector.detect()
            log.debug(f"当前状态：{self.state.name}")

            if self.state == GameState.DIALOG:
                self.handle_dialog()
            elif self.state == GameState.WAVE_START:
                self.handle_wave_start()
            elif self.state == GameState.CARD_SELECT:
                self.handle_card_select()
            elif self.state == GameState.BATTLE_RESULT:
                self.handle_battle_result()
            elif self.state == GameState.MAIN_MENU:
                log.info("检测到主界面，流程结束")
                break
            else:
                log.info("状态未知，等待1s后重试")
                time.sleep(1.0)
