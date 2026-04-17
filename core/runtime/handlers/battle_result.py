"""战斗结算页处理器。"""

from __future__ import annotations

import logging
import math

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameCoordinates, GameState

log = logging.getLogger("core.runtime.handlers.battle_result")


class BattleResultHandler:
    AP_TEMPLATE_TIMEOUT = 10.0
    AP_TEMPLATE_POLL_INTERVAL = 0.5
    RESULT_TRANSITION_TIMEOUT = 1.2
    RESULT_TRANSITION_POLL_INTERVAL = 0.2

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
            self._wait_for_result_stage_progress(stage)
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
            if getattr(self.session, "smart_battle_enabled", False):
                self.session.mark_battle_result_complete()
                self.session.stop_requested = True
                log.info("智能战斗本场已完成，已在结算后停止运行")
                return
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
            self._handle_ap_recovery_prompt()
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

    def _wait_for_result_stage_progress(self, current_stage: int) -> None:
        candidate_templates = self._result_progress_templates(current_stage)
        if not candidate_templates:
            return
        attempts = max(
            1,
            math.ceil(
                self.RESULT_TRANSITION_TIMEOUT
                / max(self.RESULT_TRANSITION_POLL_INTERVAL, 0.1)
            ),
        )
        for attempt in range(attempts):
            self.session.refresh_screen()
            screen = self.session.get_latest_screen_image()
            for filename in candidate_templates:
                if self.session.recognizer.match(
                    self.session.resources.template(filename),
                    screen,
                ):
                    return
            if attempt < attempts - 1:
                self.waiter.wait_seconds(
                    "等待结算页进入下一段",
                    self.RESULT_TRANSITION_POLL_INTERVAL,
                )
        log.warning("结算页第 %s 段点击后未快速进入下一段，已按当前画面继续", current_stage)

    def _handle_ap_recovery_prompt(self) -> None:
        self.session.refresh_screen()
        ap_recovery_pos = self.session.recognizer.match(
            self.session.resources.template("ap_recovery.png", category="ap"),
            self.session.get_latest_screen_image(),
        )
        if not ap_recovery_pos:
            return

        self.session.adb.click_raw(*GameCoordinates.AP_RECOVERY_SCROLL_POSITION)
        self.waiter.wait_seconds("已将行动力恢复列表滚到底部", 0.5)

        bronze_pos = self._wait_for_template(
            "bronzed_cobalt_fruit.png",
            category="ap",
            timeout=self.AP_TEMPLATE_TIMEOUT,
            poll_interval=self.AP_TEMPLATE_POLL_INTERVAL,
        )
        if not bronze_pos:
            raise RuntimeError("已识别到行动力恢复界面，但未识别到青铜果实。")
        self.session.adb.click_raw(*bronze_pos)
        self.waiter.wait_seconds("已点击青铜果实", 0.5)

        confirm_pos = self._wait_for_template(
            "confirm.png",
            category="ap",
            timeout=self.AP_TEMPLATE_TIMEOUT,
            poll_interval=self.AP_TEMPLATE_POLL_INTERVAL,
        )
        if not confirm_pos:
            raise RuntimeError("青铜果实数量不足，未能进入确认界面。")
        self.session.adb.click_raw(*confirm_pos)
        self.waiter.wait_seconds("已确认行动力恢复", 0.5)

    def _wait_for_template(
        self,
        filename: str,
        *,
        category: str = "common",
        timeout: float,
        poll_interval: float,
    ) -> tuple[int, int] | None:
        template_path = self.session.resources.template(filename, category=category)
        attempts = max(1, math.ceil(max(0.0, timeout) / max(poll_interval, 0.1)))
        for _ in range(attempts):
            match = self.session.recognizer.match(
                template_path,
                self.session.get_latest_screen_image(),
            )
            if match:
                return match
            self.waiter.wait_seconds(f"等待模板出现：{filename}", poll_interval)
            self.session.refresh_screen()
        return None

    @staticmethod
    def _result_progress_templates(current_stage: int) -> tuple[str, ...]:
        if current_stage == 1:
            return ("fight_result_2.png", "fight_result_3.png", "next.png")
        if current_stage == 2:
            return ("fight_result_3.png", "next.png")
        return ()
