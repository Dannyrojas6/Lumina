"""加载页处理器。"""

from __future__ import annotations

import logging

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter

log = logging.getLogger("core.runtime.handlers.loading")


class LoadingHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        log.info("检测到加载提示，等待其消失")
        tips_template = self.session.resources.template("tips.png", category="battle")
        self.waiter.wait_template_disappear(
            tips_template,
            timeout=60.0,
            poll_interval=4.0,
        )
        self.waiter.wait_screen_stable(timeout=3.0, poll_interval=0.5)
