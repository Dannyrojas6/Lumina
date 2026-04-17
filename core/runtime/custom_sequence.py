"""自定义操作序列战斗执行器。"""

from __future__ import annotations

from core.runtime.session import RuntimeSession
from core.shared.config_models import CustomSequenceAction, CustomTurnPlan


class CustomSequenceExecutor:
    """按录入动作执行自定义战斗步骤。"""

    def __init__(self, session: RuntimeSession) -> None:
        self.session = session

    def execute_turn_plan(self, plan: CustomTurnPlan) -> None:
        for action in plan.actions:
            self.execute_action(action)

    def execute_action(self, action: CustomSequenceAction) -> None:
        if action.type == "enemy_target":
            assert action.target is not None
            self.session.battle.select_enemy_target(action.target)
            return

        if action.type == "servant_skill":
            assert action.actor is not None
            assert action.skill is not None
            global_skill = self._to_global_servant_skill(action.actor, action.skill)
            self.session.battle.click_servant_skill(global_skill)
            self._resolve_optional_servant_target(
                target=action.target,
                finish=lambda target: self._finish_servant_skill(global_skill, target),
            )
            return

        if action.type == "master_skill":
            assert action.skill is not None
            self.session.battle.click_master_skill(action.skill)
            self._resolve_optional_servant_target(
                target=action.target,
                finish=lambda target: self._finish_master_skill(action.skill, target),
            )
            return

        raise RuntimeError(f"未知自定义动作类型：{action.type}")

    def _resolve_optional_servant_target(
        self,
        *,
        target: int | None,
        finish,
    ) -> None:
        has_target_window = self._has_servant_target_window()
        if target is None:
            if has_target_window:
                raise RuntimeError("录入为无己方目标，但技能实际弹出了己方选人界面")
            finish(None)
            return

        if not has_target_window:
            raise RuntimeError("录入要求选择己方目标，但技能实际没有弹出己方选人界面")
        self.session.battle.select_servant_target(target)
        finish(target)

    def _has_servant_target_window(self) -> bool:
        self.session.refresh_screen()
        match = self.session.recognizer.match(
            self.session.resources.template(
                "skill_select_servent.png",
                category="battle",
            ),
            self.session.get_latest_screen_image(),
        )
        return bool(match)

    @staticmethod
    def _to_global_servant_skill(actor: int, skill: int) -> int:
        return ((actor - 1) * 3) + skill

    def _finish_servant_skill(self, global_skill: int, target: int | None) -> None:
        if target is None:
            self.session.battle.finish_servant_skill(global_skill)
            return
        self.session.battle.finish_servant_skill(global_skill, target=target)

    def _finish_master_skill(self, skill: int, target: int | None) -> None:
        if target is None:
            self.session.battle.finish_master_skill(skill)
            return
        self.session.battle.finish_master_skill(skill, target=target)
