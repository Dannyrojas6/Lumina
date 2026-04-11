"""智能战斗判断器。"""

from __future__ import annotations

from core.battle_runtime.planner_models import (
    BattleDecision,
    BattleDecisionAction,
    BattleSnapshot,
    FrontlineServantConfig,
    ServantManifest,
    ServantSkillDefinition,
    WaveActionRule,
)


class SmartBattlePlanner:
    """基于前排配置、从者资料和当前快照生成回合动作。"""

    def __init__(
        self,
        frontline: list[FrontlineServantConfig],
        manifests: dict[str, ServantManifest],
        wave_plan: dict[int, list[WaveActionRule]],
        *,
        fail_mode: str = "conservative",
        np_ready_value: int = 100,
    ) -> None:
        self.frontline = frontline
        self.manifests = manifests
        self.wave_plan = wave_plan
        self.fail_mode = fail_mode
        self.np_ready_value = np_ready_value
        self._frontline_by_slug = {item.servant: item for item in frontline}

    def decide(self, snapshot: BattleSnapshot) -> BattleDecision:
        """根据当前快照决定这一轮应尝试的技能动作。"""
        attacker_slot = self._attacker_slot()
        if attacker_slot is None:
            return BattleDecision(
                reason="未配置主打手，已保守继续",
                fallback_used=True,
            )

        wave_rules = self.wave_plan.get(snapshot.wave_index, [])
        if not wave_rules:
            return BattleDecision(
                reason=f"第 {snapshot.wave_index} 面未配置智能动作，已保守继续",
                fallback_used=True,
            )

        attacker_np = snapshot.frontline_np.get(attacker_slot, 0)
        if not snapshot.attacker_np_known:
            return BattleDecision(
                reason="主打手 NP 读取不稳，已保守继续",
                fallback_used=True,
            )
        if not snapshot.wave_known:
            return BattleDecision(
                reason="波次读取不稳，已保守继续",
                fallback_used=True,
            )
        attacker_ready = attacker_np >= self.np_ready_value
        actions: list[BattleDecisionAction] = []

        for rule in wave_rules:
            frontline_entry = self._resolve_frontline_entry(rule.actor)
            if frontline_entry is None:
                continue

            manifest = self.manifests.get(frontline_entry.servant)
            if manifest is None:
                continue

            skill = manifest.skill_by_index(rule.skill)
            if skill is None:
                continue

            if attacker_ready and self._is_charge_skill(skill):
                continue

            if not self._conditions_match(
                condition_tags=rule.condition_tags,
                snapshot=snapshot,
                attacker_ready=attacker_ready,
            ):
                continue

            global_skill = self._global_skill_index(
                frontline_entry.slot, skill.skill_index
            )
            if global_skill in snapshot.used_skills:
                continue
            if not snapshot.skill_availability.get(global_skill, False):
                continue

            actions.append(
                BattleDecisionAction(
                    actor_slot=frontline_entry.slot,
                    actor=frontline_entry.servant,
                    skill=skill.skill_index,
                    global_skill=global_skill,
                    target=self._resolve_target(skill.target_type, attacker_slot),
                )
            )

        if actions:
            return BattleDecision(
                actions=actions,
                reason=f"第 {snapshot.wave_index} 面已生成 {len(actions)} 个技能动作",
                fallback_used=False,
            )

        if attacker_ready:
            return BattleDecision(
                reason="主打手 NP 已满，本回合直接进入出卡",
                fallback_used=False,
            )

        return BattleDecision(
            reason="当前没有满足条件的可用技能，已保守继续",
            fallback_used=self.fail_mode == "conservative",
        )

    def _attacker_slot(self) -> int | None:
        """返回前排主打手槽位。"""
        for item in self.frontline:
            if item.role == "attacker":
                return item.slot
        return None

    def _resolve_frontline_entry(
        self,
        actor: int | str,
    ) -> FrontlineServantConfig | None:
        """根据槽位号或从者名解析前排配置。"""
        if isinstance(actor, str) and actor.isdigit():
            actor = int(actor)
        if isinstance(actor, int):
            for item in self.frontline:
                if item.slot == actor:
                    return item
            return None
        return self._frontline_by_slug.get(str(actor))

    def _resolve_target(
        self,
        target_type: str,
        attacker_slot: int,
    ) -> int | None:
        """根据技能目标类型推导默认目标。"""
        if target_type in {"ally_single", "single_ally"}:
            return attacker_slot
        return None

    @staticmethod
    def _global_skill_index(slot: int, skill_index: int) -> int:
        """将前排槽位和本地技能序号转换成 1-9 的全局技能号。"""
        return (slot - 1) * 3 + skill_index

    @staticmethod
    def _is_charge_skill(skill: ServantSkillDefinition) -> bool:
        """判断技能是否属于 NP 充能类。"""
        return any("np_charge" in tag for tag in skill.effect_tags)

    def _conditions_match(
        self,
        *,
        condition_tags: list[str],
        snapshot: BattleSnapshot,
        attacker_ready: bool,
    ) -> bool:
        """判断当前动作是否满足全部条件。"""
        for tag in condition_tags:
            if tag == "np_not_ready" and attacker_ready:
                return False
            if tag == "np_ready" and not attacker_ready:
                return False
            if tag.startswith("enemy_count_eq_"):
                if not snapshot.enemy_count_known:
                    return False
                expected = int(tag.removeprefix("enemy_count_eq_"))
                if snapshot.enemy_count != expected:
                    return False
            if tag.startswith("enemy_count_gte_"):
                if not snapshot.enemy_count_known:
                    return False
                expected = int(tag.removeprefix("enemy_count_gte_"))
                if snapshot.enemy_count < expected:
                    return False
            if tag.startswith("enemy_count_lte_"):
                if not snapshot.enemy_count_known:
                    return False
                expected = int(tag.removeprefix("enemy_count_lte_"))
                if snapshot.enemy_count > expected:
                    return False
            if tag.startswith("wave_eq_"):
                expected = int(tag.removeprefix("wave_eq_"))
                if snapshot.wave_index != expected:
                    return False
            if tag.startswith("turn_eq_"):
                if not snapshot.turn_known:
                    return False
                expected = int(tag.removeprefix("turn_eq_"))
                if snapshot.current_turn != expected:
                    return False
            if tag.startswith("turn_gte_"):
                if not snapshot.turn_known:
                    return False
                expected = int(tag.removeprefix("turn_gte_"))
                if snapshot.current_turn < expected:
                    return False
            if tag.startswith("turn_lte_"):
                if not snapshot.turn_known:
                    return False
                expected = int(tag.removeprefix("turn_lte_"))
                if snapshot.current_turn > expected:
                    return False
        return True
