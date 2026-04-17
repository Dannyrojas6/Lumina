"""战斗准备页处理器。"""

from __future__ import annotations

import logging

from core.runtime.custom_sequence import CustomSequenceExecutor
from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter

log = logging.getLogger("core.runtime.handlers.battle_ready")


class BattleReadyHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter
        self.custom_executor = CustomSequenceExecutor(session)

    def handle(self) -> None:
        if getattr(self.session, "custom_sequence_enabled", False):
            self._run_custom_sequence_turn()
            self.session.battle.attack()
            return

        if self.session.smart_battle_enabled:
            self._run_main_sequence_turn(log_reason="进入智能战斗 v0.0.1，开始释放预设技能")
            self.session.battle.attack()
            return

        self._run_main_sequence_turn(log_reason="进入战斗流程，开始释放预设技能")
        self.session.battle.attack()

    def _run_main_sequence_turn(self, *, log_reason: str) -> None:
        if not self.session.battle_actions_done:
            actions = self.session.config.battle_actions()
            if actions:
                log.info(log_reason)
                for action in actions:
                    self._use_action_with_optional_target(action)
            self.session.battle_actions_done = True
            return
        log.info("检测到后续回合，跳过技能释放，直接进入攻击")

    def _run_custom_sequence_turn(self) -> None:
        if self.session.battle_snapshot_reader is None:
            raise RuntimeError("自定义操作序列模式未初始化战斗快照读取器")

        raw_snapshot = self.session.battle_snapshot_reader.read_snapshot(
            self.session.get_latest_screen_rgb()
        )
        wave = raw_snapshot.wave_index
        turn = raw_snapshot.current_turn
        if wave is None or turn is None:
            raise RuntimeError("自定义操作序列模式无法读取当前波次或回合，已停止运行")

        current_turn = (wave, turn)
        turn_plan = self.session.config.custom_sequence_battle.find_turn_plan(wave, turn)
        self.session.active_custom_turn_plan = turn_plan
        if self.session.last_processed_custom_turn == current_turn:
            log.info("自定义操作序列当前 wave=%s turn=%s 已执行过，跳过重复执行", wave, turn)
            return

        if turn_plan is None:
            log.info("自定义操作序列当前 wave=%s turn=%s 未配置动作，直接进入攻击", wave, turn)
            self.session.last_processed_custom_turn = current_turn
            return

        executor = getattr(self, "custom_executor", None)
        if executor is None:
            executor = CustomSequenceExecutor(self.session)
            self.custom_executor = executor
        executor.execute_turn_plan(turn_plan)
        self.session.last_processed_custom_turn = current_turn

    def _use_action_with_optional_target(self, action: dict) -> None:
        action_type = action["type"]
        skill_num = action["skill"]
        default_target = (
            action["target"]
            if action.get("target") is not None
            else self.session.config.default_skill_target
        )

        if action_type == "master":
            self.session.battle.click_master_skill(skill_num)
        else:
            self.session.battle.click_servant_skill(skill_num)

        self.session.refresh_screen()
        target_select_pos = self.session.recognizer.match(
            self.session.resources.template("skill_select_servent.png", category="battle"),
            self.session.get_latest_screen_image(),
        )
        if target_select_pos:
            self.session.battle.select_servant_target(default_target)
            if action_type == "master":
                self.session.battle.finish_master_skill(skill_num, target=default_target)
                return
            self.session.battle.finish_servant_skill(skill_num, target=default_target)
            return

        if action_type == "master":
            self.session.battle.finish_master_skill(skill_num)
            return
        self.session.battle.finish_servant_skill(skill_num)
