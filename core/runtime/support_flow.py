"""助战选择相关流程。"""

from __future__ import annotations

import logging
import time
from typing import Optional

from core.shared.screen_coordinates import GameCoordinates
from core.support_recognition.verifier import SupportPortraitVerifier

log = logging.getLogger("core.support_flow")


class SupportFlowMixin:
    """承载助战筛选、刷新、回退与头像核验逻辑。"""

    def handle_support_select(self) -> None:
        """处理助战选择界面，支持按职阶筛选并滑动搜索目标从者。"""
        support_cfg = self.config.support_config()
        support_class = str(support_cfg["class_name"])
        servant_name = str(support_cfg["servant"])
        pick_index = int(support_cfg["pick_index"])
        max_scroll_pages = int(support_cfg["max_scroll_pages"])

        self._select_support_class(support_class)

        if servant_name:
            if self._search_and_pick_support(servant_name, max_scroll_pages):
                return

            if self._refresh_support_list():
                if self._search_and_pick_support(servant_name, max_scroll_pages):
                    return

            log.warning(
                "未找到目标助战=%s，刷新后仍未命中，回退到默认助战位",
                servant_name,
            )

        self._fallback_pick_support(pick_index)

    def _search_and_pick_support(
        self, servant_name: str, max_scroll_pages: int
    ) -> bool:
        """搜索目标助战，命中后直接点击。"""
        support_pos = self._find_support_on_current_page(servant_name)
        if support_pos:
            self.adb.click(*support_pos)
            time.sleep(self.SUPPORT_CLICK_DELAY)
            log.info("检测到目标助战=%s，已点击进入", servant_name)
            return True

        for page in range(1, max_scroll_pages + 1):
            self._scroll_support_list()
            support_pos = self._find_support_on_current_page(servant_name)
            if support_pos:
                self.adb.click(*support_pos)
                time.sleep(self.SUPPORT_CLICK_DELAY)
                log.info(
                    "滑动第 %s 页后识别到目标助战=%s，已点击进入",
                    page,
                    servant_name,
                )
                return True

        log.warning(
            "未找到目标助战=%s，已超过最大搜索页数=%s",
            servant_name,
            max_scroll_pages,
        )
        return False

    def _select_support_class(self, support_class: str) -> None:
        """点击助战职阶筛选按钮。"""
        if support_class not in {"all", "berserker"}:
            log.warning(
                "当前仅支持 all / berserker，收到 class=%s，已回退为 all",
                support_class,
            )
            support_class = "all"

        class_template = self.resources.support_class_template(support_class)
        class_pos = self.recognizer.match(
            class_template,
            self._get_latest_screen_image(),
        )
        if class_pos:
            self.adb.click(*class_pos)
            time.sleep(self.SUPPORT_CLICK_DELAY)
            self._refresh_screen()
            log.info("检测到助战选择界面，已切换到职阶=%s", support_class)
            return

        if support_class != "all":
            log.warning(
                "未识别到职阶=%s 的模板按钮，回退尝试 all",
                support_class,
            )
            all_class_pos = self.recognizer.match(
                self.resources.support_class_template("all"),
                self._get_latest_screen_image(),
            )
            if all_class_pos:
                self.adb.click(*all_class_pos)
                time.sleep(self.SUPPORT_CLICK_DELAY)
                self._refresh_screen()
                log.info("已回退到全职阶筛选")
                return
        log.warning("助战页未识别到目标职阶按钮，将继续尝试默认选择")

    def _find_support_on_current_page(
        self, servant_name: str
    ) -> Optional[tuple[int, int]]:
        """在当前页尝试识别目标助战人物头像。"""
        verifier = self._get_support_verifier(servant_name)
        if verifier is None:
            return None
        initial_screen = self._get_latest_screen_rgb()
        time.sleep(self.config.support.recognition.confirm_delay)
        self._refresh_screen()
        confirmed_screen = self._get_latest_screen_rgb()
        match_result = verifier.confirm_match(initial_screen, confirmed_screen)
        if match_result:
            log.debug(
                "助战头像命中 servant=%s slot=%s score=%.3f confirm=%.3f margin=%.3f",
                servant_name,
                match_result.slot_index,
                match_result.score,
                match_result.confirm_score,
                match_result.margin,
            )
            return match_result.click_position
        return None

    def _get_support_verifier(
        self, servant_name: str
    ) -> Optional[SupportPortraitVerifier]:
        """按需加载目标从者的人物头像核验器。"""
        if servant_name in self._support_verifiers:
            return self._support_verifiers[servant_name]
        try:
            verifier = SupportPortraitVerifier.from_servant(
                servant_name=servant_name,
                resources=self.resources,
                config=self.config.support.recognition,
            )
        except (FileNotFoundError, ValueError) as exc:
            log.warning("助战头像核验器未启用 servant=%s reason=%s", servant_name, exc)
            return None
        self._support_verifiers[servant_name] = verifier
        return verifier

    def _scroll_support_list(self) -> None:
        """向上滑动助战列表，进入下一页搜索。"""
        self.adb.swipe(
            GameCoordinates.SUPPORT_SCROLL_START[0],
            GameCoordinates.SUPPORT_SCROLL_START[1],
            GameCoordinates.SUPPORT_SCROLL_END[0],
            GameCoordinates.SUPPORT_SCROLL_END[1],
            duration=0.2,
        )
        time.sleep(self.SUPPORT_CLICK_DELAY)
        self._refresh_screen()
        log.info("当前页未命中目标助战，已执行一次助战列表滑动")

    def _refresh_support_list(self) -> bool:
        """点击列表更新并确认，等待助战列表重新加载。"""
        list_update_pos = self.recognizer.match(
            self.resources.template("list_update.png", category="support_select"),
            self._get_latest_screen_image(),
        )
        if not list_update_pos:
            log.warning("未识别到助战列表更新按钮，跳过刷新重试")
            return False

        self.adb.click(*list_update_pos)
        time.sleep(self.DEFAULT_CLICK_DELAY)
        self._refresh_screen()

        yes_pos = self.recognizer.match(
            self.resources.template("yes.png"),
            self._get_latest_screen_image(),
        )
        if not yes_pos:
            log.warning("助战列表更新确认框未识别到“是”按钮，跳过刷新重试")
            return False

        self.adb.click(*yes_pos)
        log.info("已点击助战列表更新，并确认刷新")
        time.sleep(self.SUPPORT_REFRESH_WAIT)
        self._refresh_screen()
        return True

    def _fallback_pick_support(self, pick_index: int) -> None:
        """回退到默认助战位选择，保证流程不中断。"""
        support_pos = GameCoordinates.SUPPORT_POSITIONS.get(pick_index)
        if support_pos is None:
            log.warning("无效助战序号=%s，回退到第 1 位", pick_index)
            support_pos = GameCoordinates.SUPPORT_POSITIONS[1]

        self.adb.click(*support_pos)
        time.sleep(self.SUPPORT_CLICK_DELAY)
        log.info("已回退选择默认助战位=%s", pick_index)
