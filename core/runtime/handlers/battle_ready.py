"""战斗准备页处理器。"""

from __future__ import annotations

import logging

from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter

log = logging.getLogger("core.runtime.handlers.battle_ready")


class BattleReadyHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        if self.session.smart_battle_enabled:
            self._run_smart_battle_turn()
            self.session.battle.attack()
            return

        if not self.session.battle_actions_done:
            actions = self.session.config.battle_actions()
            if actions:
                log.info("进入战斗流程，开始释放预设技能")
                for action in actions:
                    self._use_action_with_optional_target(action)
            self.session.battle_actions_done = True
        else:
            log.info("检测到后续回合，跳过技能释放，直接进入攻击")

        self.session.battle.attack()

    def _run_smart_battle_turn(self) -> None:
        if (
            self.session.battle_snapshot_reader is None
            or self.session.smart_battle_planner is None
        ):
            log.warning("智能战斗未完整初始化，已保守继续")
            return

        try:
            raw_snapshot = self.session.battle_snapshot_reader.read_snapshot(
                self.session.get_latest_screen_rgb()
            )
            snapshot = self.session.build_smart_snapshot(raw_snapshot)
            decision = self.session.smart_battle_planner.decide(snapshot)
        except Exception as exc:
            log.warning("智能战斗识别失败，已保守继续：%s", exc)
            return

        log.info(
            "智能战斗 wave=%s turn=%s enemy=%s reason=%s fallback=%s",
            snapshot.wave_index,
            snapshot.current_turn,
            snapshot.enemy_count,
            decision.reason,
            decision.fallback_used,
        )
        if (
            snapshot.turn_known
            and self.session.last_processed_turn is not None
            and snapshot.current_turn == self.session.last_processed_turn
        ):
            log.info(
                "当前回合=%s 已执行过智能判断，本次跳过重复释放", snapshot.current_turn
            )
            return

        for action in decision.actions:
            self._use_action_with_optional_target(
                {
                    "type": action.action_type,
                    "skill": action.global_skill,
                    "target": action.target,
                }
            )
            self.session.used_servant_skills.add(action.global_skill)
        if snapshot.turn_known:
            self.session.last_processed_turn = snapshot.current_turn

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
