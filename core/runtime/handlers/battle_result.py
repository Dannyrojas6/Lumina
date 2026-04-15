"""战斗结算页处理器。"""

from __future__ import annotations

import logging

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameCoordinates, GameState

log = logging.getLogger("core.runtime.handlers.battle_result")


class BattleResultHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        if not self.waiter.confirm_state_entry(GameState.BATTLE_RESULT):
            log.warning("结算页在超时内未稳定，已按当前画面继续处理")

        stage = self._detect_battle_result_stage()
        if stage in {1, 2}:
            self.session.adb.click(*GameCoordinates.RESULT_CONTINUE)
            self.waiter.wait_seconds(f"已点击结算页第 {stage} 段继续", 0.5)
            self.waiter.wait_screen_stable(timeout=3.0, poll_interval=0.5)
            return

        if stage == 3:
            next_pos = self.session.recognizer.match(
                self.session.resources.template("next.png"),
                self.session.get_latest_screen_image(),
            )
            if not next_pos:
                log.warning("已识别到战利品结算页，但未识别到下一步按钮")
                return
            self.session.adb.click_raw(*next_pos)
            self.waiter.wait_seconds("已点击结算页下一步", 0.5)
            self.waiter.wait_seconds("等待结算完成收尾", 1.0)
            if not self._handle_continue_battle_prompt():
                return
            self.session.mark_battle_result_complete()
            log.info("战斗结果处理完成")
            return

        log.warning("已进入结算状态，但未识别到具体结果页阶段")

    def _detect_battle_result_stage(self) -> int | None:
        for stage in (1, 2, 3):
            pos = self.session.recognizer.match(
                self.session.resources.template(f"fight_result_{stage}.png"),
                self.session.get_latest_screen_image(),
            )
            if pos:
                return stage
        return None

    def _handle_continue_battle_prompt(self) -> bool:
        self.session.refresh_screen()
        screen = self.session.get_latest_screen_image()
        continue_pos = self.session.recognizer.match(
            self.session.resources.template("continue_battle.png"),
            screen,
        )
        if not continue_pos:
            return True

        if self.session.config.continue_battle:
            self.session.adb.click_raw(*continue_pos)
            self.waiter.wait_seconds("已点击连续出击", 0.5)
            return True

        close_pos = self.session.recognizer.match(
            self.session.resources.template("close.png"),
            screen,
        )
        if not close_pos:
            log.warning("已识别到连续出击界面，但未识别到关闭按钮")
            return False
        self.session.adb.click_raw(*close_pos)
        self.waiter.wait_seconds("已关闭连续出击界面", 0.5)
        return True
