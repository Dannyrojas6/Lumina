"""队伍确认处理器。"""

from __future__ import annotations

import logging

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter

log = logging.getLogger("core.runtime.handlers.team_confirm")


class TeamConfirmHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        start_pos = self.session.recognizer.match(
            self.session.resources.template("start_task.png", category="team_confirm"),
            self.session.get_latest_screen_image(),
        )
        if not start_pos:
            return
        self.session.adb.click(*start_pos)
        self.waiter.wait_seconds("检测到队伍确认界面，已点击开始任务", 0.5)
