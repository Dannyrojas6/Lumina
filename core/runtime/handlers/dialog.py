"""对话与确认弹窗处理器。"""

from __future__ import annotations

import logging

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter

log = logging.getLogger("core.runtime.handlers.dialog")


class DialogHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        pos = self.session.recognizer.match(
            self.session.resources.template("skip.png"),
            self.session.get_latest_screen_image(),
        )
        if not pos:
            return
        self.session.adb.click(*pos)
        self.waiter.wait_seconds("已点击跳过对话", 0.5)
        self.session.refresh_screen()
        yes_pos = self.session.recognizer.match(
            self.session.resources.template("yes.png"),
            self.session.get_latest_screen_image(),
        )
        if yes_pos:
            self.session.adb.click(*yes_pos)
            self.waiter.wait_seconds("已确认跳过对话", 0.5)
        log.info("跳过对话")
