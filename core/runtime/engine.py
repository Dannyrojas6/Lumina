"""运行时主引擎。"""

from __future__ import annotations

import logging

from core.perception import StateDetector
from core.runtime.handlers import (
    BattleReadyHandler,
    BattleResultHandler,
    CardSelectHandler,
    DialogHandler,
    LoadingHandler,
    MainMenuHandler,
    SupportSelectHandler,
    TeamConfirmHandler,
    UnknownHandler,
)
from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameState

log = logging.getLogger("core.runtime.engine")


class AutomationEngine:
    """管理一次自动刷本流程的高层状态机。"""

    HOT_STATE_CANDIDATES: dict[GameState, tuple[GameState, ...]] = {
        GameState.MAIN_MENU: (
            GameState.MAIN_MENU,
            GameState.SUPPORT_SELECT,
            GameState.DIALOG,
            GameState.LOADING_TIPS,
        ),
        GameState.SUPPORT_SELECT: (
            GameState.SUPPORT_SELECT,
            GameState.TEAM_CONFIRM,
            GameState.DIALOG,
            GameState.LOADING_TIPS,
        ),
        GameState.TEAM_CONFIRM: (
            GameState.TEAM_CONFIRM,
            GameState.LOADING_TIPS,
            GameState.BATTLE_READY,
            GameState.DIALOG,
        ),
        GameState.LOADING_TIPS: (
            GameState.LOADING_TIPS,
            GameState.BATTLE_READY,
            GameState.DIALOG,
            GameState.BATTLE_RESULT,
        ),
        GameState.BATTLE_READY: (
            GameState.BATTLE_READY,
            GameState.CARD_SELECT,
            GameState.BATTLE_RESULT,
            GameState.DIALOG,
            GameState.LOADING_TIPS,
        ),
        GameState.CARD_SELECT: (
            GameState.CARD_SELECT,
            GameState.BATTLE_READY,
            GameState.BATTLE_RESULT,
            GameState.DIALOG,
            GameState.LOADING_TIPS,
        ),
        GameState.BATTLE_RESULT: (
            GameState.BATTLE_RESULT,
            GameState.SUPPORT_SELECT,
            GameState.MAIN_MENU,
            GameState.DIALOG,
            GameState.LOADING_TIPS,
        ),
        GameState.DIALOG: (
            GameState.DIALOG,
            GameState.SUPPORT_SELECT,
            GameState.TEAM_CONFIRM,
            GameState.BATTLE_READY,
            GameState.BATTLE_RESULT,
            GameState.MAIN_MENU,
        ),
    }

    def __init__(self, session: RuntimeSession) -> None:
        self.session = session
        self.state_detector = StateDetector(
            recognizer=session.recognizer,
            screen_callback=session.refresh_screen,
            resources=session.resources,
            screen_array_callback=session.get_latest_screen_image,
        )
        self.waiter = Waiter(session, self.state_detector)
        self.handlers = {
            GameState.MAIN_MENU: MainMenuHandler(session, self.waiter),
            GameState.SUPPORT_SELECT: SupportSelectHandler(session, self.waiter),
            GameState.TEAM_CONFIRM: TeamConfirmHandler(session, self.waiter),
            GameState.LOADING_TIPS: LoadingHandler(session, self.waiter),
            GameState.DIALOG: DialogHandler(session, self.waiter),
            GameState.BATTLE_READY: BattleReadyHandler(session, self.waiter),
            GameState.CARD_SELECT: CardSelectHandler(session, self.waiter),
            GameState.BATTLE_RESULT: BattleResultHandler(session, self.waiter),
        }
        self.unknown_handler = UnknownHandler(session, self.waiter)

    def run(self) -> None:
        """循环识别界面状态，并分派给对应处理器。"""
        log.info("脚本启动，进入主循环")
        max_loops = self.session.config.loop_count
        while max_loops < 0 or self.session.loop_done < max_loops:
            detection = self.state_detector.detect(
                candidates=self._candidate_states(self.session.state)
            )
            self.session.state = detection.state
            state_changed_callback = getattr(self.session, "on_state_changed", None)
            if state_changed_callback is not None:
                state_changed_callback(detection.state)
            if detection.state != GameState.UNKNOWN:
                self.session.consecutive_unknown_count = 0
                self.session.unknown_snapshot_saved = False
            log.debug("当前状态：%s", self.session.state.name)
            handler = self.handlers.get(self.session.state)
            if handler is None:
                self.unknown_handler.handle(detection)
                self.waiter.wait_seconds("等待下一次状态识别", 0.5)
                continue
            handler.handle()
            if self.session.stop_requested:
                log.info("收到停止标记，主循环结束")
                break

    def _candidate_states(self, current_state: GameState) -> tuple[GameState, ...] | None:
        return self.HOT_STATE_CANDIDATES.get(current_state)
