"""战斗结算页处理器。"""

from __future__ import annotations

import logging
import math

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameCoordinates, GameState

log = logging.getLogger("core.runtime.handlers.battle_result")


def wait_for_template(
    session: RuntimeSession,
    waiter: Waiter,
    filename: str,
    *,
    category: str = "common",
    timeout: float,
    poll_interval: float,
) -> tuple[int, int] | None:
    template_path = session.resources.template(filename, category=category)
    attempts = max(1, math.ceil(max(0.0, timeout) / max(poll_interval, 0.1)))
    for attempt in range(attempts):
        if getattr(session, "stop_requested", False):
            return None
        match = session.recognizer.match(
            template_path,
            session.get_latest_screen_image(),
        )
        if match:
            return match
        if attempt < attempts - 1:
            waiter.wait_seconds(f"等待模板出现：{filename}", poll_interval)
            if getattr(session, "stop_requested", False):
                return None
            session.refresh_screen()
    return None


def handle_ap_recovery_prompt(
    session: RuntimeSession,
    waiter: Waiter,
    *,
    appear_timeout: float,
    appear_poll_interval: float,
    template_timeout: float,
    template_poll_interval: float,
    destination_timeout: float,
    destination_poll_interval: float,
) -> bool:
    ap_recovery_pos = wait_for_template(
        session,
        waiter,
        "ap_recovery.png",
        category="ap",
        timeout=appear_timeout,
        poll_interval=appear_poll_interval,
    )
    if not ap_recovery_pos:
        return False

    session.adb.click_raw(*GameCoordinates.AP_RECOVERY_SCROLL_POSITION)
    waiter.wait_seconds("已将行动力恢复列表滚到底部", 0.5)

    bronze_pos = wait_for_template(
        session,
        waiter,
        "bronzed_cobalt_fruit.png",
        category="ap",
        timeout=template_timeout,
        poll_interval=template_poll_interval,
    )
    if not bronze_pos:
        if getattr(session, "stop_requested", False):
            return True
        raise RuntimeError("已识别到行动力恢复界面，但未识别到青铜果实。")
    session.adb.click_raw(*bronze_pos)
    waiter.wait_seconds("已点击青铜果实", 0.5)

    confirm_pos = wait_for_template(
        session,
        waiter,
        "confirm.png",
        category="ap",
        timeout=template_timeout,
        poll_interval=template_poll_interval,
    )
    if not confirm_pos:
        if getattr(session, "stop_requested", False):
            return True
        raise RuntimeError("青铜果实数量不足，未能进入确认界面。")
    session.adb.click_raw(*confirm_pos)
    waiter.wait_seconds("已确认行动力恢复", 0.5)
    wait_for_post_ap_recovery_destination(
        session,
        waiter,
        timeout=destination_timeout,
        poll_interval=destination_poll_interval,
    )
    return True


def wait_for_post_ap_recovery_destination(
    session: RuntimeSession,
    waiter: Waiter,
    *,
    timeout: float,
    poll_interval: float,
) -> None:
    support_select_template = session.resources.state_templates[GameState.SUPPORT_SELECT]
    loading_tips_template = session.resources.state_templates[GameState.LOADING_TIPS]
    attempts = max(1, math.ceil(max(0.0, timeout) / max(poll_interval, 0.1)))
    for attempt in range(attempts):
        if getattr(session, "stop_requested", False):
            return
        session.refresh_screen()
        screen = session.get_latest_screen_image()
        if session.recognizer.match(support_select_template, screen):
            log.info("行动力恢复后已进入助战选择界面")
            return
        if session.recognizer.match(loading_tips_template, screen):
            log.info("行动力恢复后已进入加载界面")
            return
        if attempt < attempts - 1:
            waiter.wait_seconds("等待行动力恢复后续界面", poll_interval)
            if getattr(session, "stop_requested", False):
                return
    raise RuntimeError("行动力恢复确认后未在超时内进入下一轮界面，已停止运行。")


class BattleResultHandler:
    AP_APPEAR_TIMEOUT = 0.5
    AP_APPEAR_POLL_INTERVAL = 0.25
    AP_TEMPLATE_TIMEOUT = 10.0
    AP_TEMPLATE_POLL_INTERVAL = 0.5
    AP_DESTINATION_TIMEOUT = 45.0
    AP_DESTINATION_POLL_INTERVAL = 0.5
    POST_CONTINUE_TIMEOUT = 45.0
    POST_CONTINUE_POLL_INTERVAL = 0.5
    RESULT_TRANSITION_TIMEOUT = 45.0
    RESULT_TRANSITION_POLL_INTERVAL = 0.5

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
            self._wait_for_continue_battle_destination()
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
            if getattr(self.session, "stop_requested", False):
                return
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
                    "等待结算页后续界面",
                    self.RESULT_TRANSITION_POLL_INTERVAL,
                )
                if getattr(self.session, "stop_requested", False):
                    return
        if getattr(self.session, "stop_requested", False):
            return
        raise RuntimeError(
            f"结算页第 {current_stage} 段点击后未进入下一段，已停止运行。"
        )

    def _handle_ap_recovery_prompt(self) -> None:
        self.session.refresh_screen()
        handle_ap_recovery_prompt(
            self.session,
            self.waiter,
            appear_timeout=self.AP_APPEAR_TIMEOUT,
            appear_poll_interval=self.AP_APPEAR_POLL_INTERVAL,
            template_timeout=self.AP_TEMPLATE_TIMEOUT,
            template_poll_interval=self.AP_TEMPLATE_POLL_INTERVAL,
            destination_timeout=self.AP_DESTINATION_TIMEOUT,
            destination_poll_interval=self.AP_DESTINATION_POLL_INTERVAL,
        )

    def _wait_for_continue_battle_destination(self) -> None:
        support_select_template = self.session.resources.state_templates[
            GameState.SUPPORT_SELECT
        ]
        attempts = max(
            1,
            math.ceil(
                self.POST_CONTINUE_TIMEOUT
                / max(self.POST_CONTINUE_POLL_INTERVAL, 0.1)
            ),
        )
        for attempt in range(attempts):
            if getattr(self.session, "stop_requested", False):
                return
            self.session.refresh_screen()
            screen = self.session.get_latest_screen_image()
            if self.session.recognizer.match(support_select_template, screen):
                log.info("连续出击后已进入助战选择界面")
                return
            if self.session.recognizer.match(
                self.session.resources.template("ap_recovery.png", category="ap"),
                screen,
            ):
                handle_ap_recovery_prompt(
                    self.session,
                    self.waiter,
                    appear_timeout=0.0,
                    appear_poll_interval=self.AP_APPEAR_POLL_INTERVAL,
                    template_timeout=self.AP_TEMPLATE_TIMEOUT,
                    template_poll_interval=self.AP_TEMPLATE_POLL_INTERVAL,
                    destination_timeout=self.AP_DESTINATION_TIMEOUT,
                    destination_poll_interval=self.AP_DESTINATION_POLL_INTERVAL,
                )
                return
            if attempt < attempts - 1:
                self.waiter.wait_seconds(
                    "等待连续出击后续界面",
                    self.POST_CONTINUE_POLL_INTERVAL,
                )
                if getattr(self.session, "stop_requested", False):
                    return
        if getattr(self.session, "stop_requested", False):
            return
        raise RuntimeError("连续出击后未在超时内进入助战选择或行动力恢复界面，已停止运行。")

    @staticmethod
    def _result_progress_templates(current_stage: int) -> tuple[str, ...]:
        if current_stage == 1:
            return ("fight_result_2.png", "fight_result_3.png", "next.png")
        if current_stage == 2:
            return ("fight_result_3.png", "next.png")
        return ()
