"""助战选择处理器。"""

from __future__ import annotations

import logging

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameCoordinates, GameState

log = logging.getLogger("core.runtime.handlers.support_select")


class SupportSelectHandler:
    SUPPORT_TRANSITION_TIMEOUT = 4.0
    SUPPORT_TRANSITION_POLL_INTERVAL = 0.3
    SUPPORT_STABLE_TIMEOUT = 1.5
    SUPPORT_STABLE_POLL_INTERVAL = 0.25

    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        if not self.waiter.confirm_state_entry(GameState.SUPPORT_SELECT):
            log.warning("助战列表在超时内未稳定，已按当前画面继续处理")

        support_cfg = self.session.config.support
        support_class = str(support_cfg.class_name)
        servant_name = str(support_cfg.servant)
        pick_index = int(support_cfg.pick_index)
        max_scroll_pages = int(support_cfg.max_scroll_pages)
        self._select_support_class(support_class)

        if servant_name:
            if self._search_and_pick_support(servant_name, max_scroll_pages):
                return
            if self._refresh_support_list() and self._search_and_pick_support(
                servant_name, max_scroll_pages
            ):
                return
            log.warning(
                "未找到目标助战=%s，刷新后仍未命中，回退到默认助战位",
                servant_name,
            )

        self._fallback_pick_support(pick_index)

    def _search_and_pick_support(
        self,
        servant_name: str,
        max_scroll_pages: int,
    ) -> bool:
        support_pos = self._find_support_on_current_page(servant_name)
        if support_pos:
            self.session.adb.click(*support_pos)
            self._wait_after_support_click(
                f"检测到目标助战={servant_name}，已点击进入"
            )
            return True

        for page in range(1, max_scroll_pages + 1):
            self._scroll_support_list()
            support_pos = self._find_support_on_current_page(servant_name)
            if support_pos:
                self.session.adb.click(*support_pos)
                self._wait_after_support_click(
                    f"滑动第 {page} 页后识别到目标助战={servant_name}，已点击进入"
                )
                return True

        log.warning(
            "未找到目标助战=%s，已超过最大搜索页数=%s",
            servant_name,
            max_scroll_pages,
        )
        return False

    def _select_support_class(self, support_class: str) -> None:
        if support_class not in {"all", "berserker"}:
            log.warning(
                "当前仅支持 all / berserker，收到 class=%s，已回退为 all",
                support_class,
            )
            support_class = "all"

        class_template = self.session.resources.support_class_template(support_class)
        class_pos = self.session.recognizer.match(
            class_template,
            self.session.get_latest_screen_image(),
        )
        if class_pos:
            self.session.adb.click(*class_pos)
            self.waiter.wait_seconds(f"检测到助战选择界面，已切换到职阶={support_class}", 0.5)
            self.session.refresh_screen()
            return

        if support_class != "all":
            log.warning("未识别到职阶=%s 的模板按钮，回退尝试 all", support_class)
            all_class_pos = self.session.recognizer.match(
                self.session.resources.support_class_template("all"),
                self.session.get_latest_screen_image(),
            )
            if all_class_pos:
                self.session.adb.click(*all_class_pos)
                self.waiter.wait_seconds("已回退到全职阶筛选", 0.5)
                self.session.refresh_screen()
                return
        log.warning("助战页未识别到目标职阶按钮，将继续尝试默认选择")

    def _find_support_on_current_page(
        self,
        servant_name: str,
    ) -> tuple[int, int] | None:
        verifier = self.session.get_support_verifier(servant_name)
        if verifier is None:
            return None
        initial_screen = self.session.get_latest_screen_rgb()
        self.waiter.wait_seconds("等待助战二次确认", self.session.config.support.recognition.confirm_delay)
        self.session.refresh_screen()
        confirmed_screen = self.session.get_latest_screen_rgb()
        match_result = verifier.confirm_match(initial_screen, confirmed_screen)
        if not match_result:
            return None
        log.debug(
            "助战头像命中 servant=%s slot=%s score=%.3f confirm=%.3f margin=%.3f",
            servant_name,
            match_result.slot_index,
            match_result.score,
            match_result.confirm_score,
            match_result.margin,
        )
        return match_result.click_position

    def _scroll_support_list(self) -> None:
        self.session.adb.swipe(
            GameCoordinates.SUPPORT_SCROLL_START[0],
            GameCoordinates.SUPPORT_SCROLL_START[1],
            GameCoordinates.SUPPORT_SCROLL_END[0],
            GameCoordinates.SUPPORT_SCROLL_END[1],
            duration=0.2,
        )
        self.waiter.wait_seconds("当前页未命中目标助战，已执行一次助战列表滑动", 0.5)
        self.session.refresh_screen()

    def _refresh_support_list(self) -> bool:
        list_update_pos = self.session.recognizer.match(
            self.session.resources.template("list_update.png", category="support_select"),
            self.session.get_latest_screen_image(),
        )
        if not list_update_pos:
            log.warning("未识别到助战列表更新按钮，跳过刷新重试")
            return False

        self.session.adb.click(*list_update_pos)
        self.waiter.wait_seconds("已点击助战列表更新", 0.5)
        self.session.refresh_screen()

        yes_pos = self.session.recognizer.match(
            self.session.resources.template("yes.png"),
            self.session.get_latest_screen_image(),
        )
        if not yes_pos:
            log.warning("助战列表更新确认框未识别到“是”按钮，跳过刷新重试")
            return False

        self.session.adb.click(*yes_pos)
        log.info("已点击助战列表更新，并确认刷新")
        self.waiter.wait_seconds("等待助战刷新结果", 0.5)
        self.session.refresh_screen()
        return True

    def _fallback_pick_support(self, pick_index: int) -> None:
        support_pos = GameCoordinates.SUPPORT_POSITIONS.get(pick_index)
        if support_pos is None:
            log.warning("无效助战序号=%s，回退到第 1 位", pick_index)
            support_pos = GameCoordinates.SUPPORT_POSITIONS[1]
        self.session.adb.click(*support_pos)
        self._wait_after_support_click(f"已回退选择默认助战位={pick_index}")

    def _wait_after_support_click(self, reason: str) -> None:
        self.waiter.wait_seconds(reason, 0.3)
        detection = self.waiter.wait_state_exit(
            {GameState.SUPPORT_SELECT, GameState.UNKNOWN},
            timeout=self.SUPPORT_TRANSITION_TIMEOUT,
            poll_interval=self.SUPPORT_TRANSITION_POLL_INTERVAL,
        )
        if detection is None:
            raise RuntimeError("助战点击后未在超时内离开列表，已停止运行。")
