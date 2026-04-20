"""主菜单处理器。"""

from __future__ import annotations

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameCoordinates


class MainMenuHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        quest_slot = self.session.config.quest_slot
        quest_pos = GameCoordinates.QUEST_SLOTS.get(quest_slot)
        if quest_pos is None:
            raise RuntimeError(f"无效关卡槽位={quest_slot}，请检查配置。")
        self.session.adb.click(*quest_pos)
        self.waiter.wait_seconds("检测到主菜单，已点击关卡入口", 0.5)
