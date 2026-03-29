"""智能战斗判断层，负责根据战场快照生成当前回合动作。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SkillTargetType = Literal["team", "self", "ally_single"]
ServantRole = Literal["attacker", "support", "hybrid"]


@dataclass(frozen=True)
class FrontlineServantConfig:
    """描述前排三位从者的身份信息。"""

    slot: int
    servant: str
    role: ServantRole
    is_support: bool = False


@dataclass(frozen=True)
class ServantSkillDefinition:
    """描述单个技能的基础资料。"""

    skill_index: int
    effect_tags: list[str] = field(default_factory=list)
    target_type: SkillTargetType = "team"
    priority_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ServantManifest:
    """描述单个从者的最小可用资料。"""

    slug: str
    display_name: str
    role_tags: list[str] = field(default_factory=list)
    skills: list[ServantSkillDefinition] = field(default_factory=list)

    def skill_by_index(self, skill_index: int) -> ServantSkillDefinition | None:
        """返回指定序号的技能定义。"""
        for skill in self.skills:
            if skill.skill_index == skill_index:
                return skill
        return None


@dataclass(frozen=True)
class WaveActionRule:
    """描述某一面里可尝试执行的一步动作。"""

    actor: int | str
    skill: int
    condition_tags: list[str] = field(default_factory=list)
    phase: str | None = None


@dataclass(frozen=True)
class BattleSnapshot:
    """描述当前回合判断层真正依赖的战场事实。"""

    wave_index: int
    enemy_count: int
    current_turn: int
    frontline_np: dict[int, int]
    skill_availability: dict[int, bool]
    used_skills: set[int] = field(default_factory=set)
    attacker_np_known: bool = True
    wave_known: bool = True
    enemy_count_known: bool = True
    turn_known: bool = True


@dataclass(frozen=True)
class BattleDecisionAction:
    """描述一条将交给主流程执行的动作。"""

    action_type: Literal["servant"] = "servant"
    actor_slot: int = 1
    skill: int = 1
    global_skill: int = 1
    target: int | None = None
    actor: str = ""


@dataclass(frozen=True)
class BattleDecision:
    """描述本回合的整体判断结果。"""

    actions: list[BattleDecisionAction] = field(default_factory=list)
    reason: str = ""
    fallback_used: bool = False


def normalize_frontline(frontline: list[Any]) -> list[FrontlineServantConfig]:
    """将配置层的 frontline 结构转换成判断层结构。"""
    normalized: list[FrontlineServantConfig] = []
    for item in frontline:
        normalized.append(
            FrontlineServantConfig(
                slot=int(_read_attr(item, "slot")),
                servant=str(_read_attr(item, "servant")),
                role=str(_read_attr(item, "role")),
                is_support=bool(_read_attr(item, "is_support", False)),
            )
        )
    return normalized


def normalize_wave_plan(wave_plan: list[Any]) -> dict[int, list[WaveActionRule]]:
    """将配置层的 wave_plan 结构转换成判断层结构。"""
    normalized: dict[int, list[WaveActionRule]] = {}
    for item in wave_plan:
        wave_index = int(_read_attr(item, "wave"))
        raw_actions = list(_read_attr(item, "actions", []))
        normalized[wave_index] = [
            WaveActionRule(
                actor=_read_attr(action, "actor"),
                skill=int(_read_attr(action, "skill")),
                condition_tags=[
                    str(tag) for tag in list(_read_attr(action, "condition_tags", []))
                ],
                phase=str(_read_attr(action, "phase", "buff")),
            )
            for action in raw_actions
        ]
    return normalized


def normalize_manifests(manifests: list[Any]) -> dict[str, ServantManifest]:
    """将资源层从者资料转换成判断层结构。"""
    normalized: dict[str, ServantManifest] = {}
    for item in manifests:
        if item is None:
            continue
        slug = str(_read_attr(item, "servant_name", _read_attr(item, "slug")))
        raw_skills = list(_read_attr(item, "skills", []))
        normalized[slug] = ServantManifest(
            slug=slug,
            display_name=str(_read_attr(item, "display_name", slug)),
            role_tags=[str(_read_attr(item, "role", ""))],
            skills=[
                ServantSkillDefinition(
                    skill_index=int(_read_attr(skill, "skill_index")),
                    effect_tags=[
                        str(tag) for tag in list(_read_attr(skill, "effect_tags", []))
                    ],
                    target_type=str(_read_attr(skill, "target_type", "team")),
                    priority_tags=[
                        str(tag)
                        for tag in list(_read_attr(skill, "priority_tags", []))
                    ],
                )
                for skill in raw_skills
            ],
        )
    return normalized


def _read_attr(item: Any, key: str, default: Any = None) -> Any:
    """兼容 dataclass、普通对象和 dict 的统一读值。"""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


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

            global_skill = self._global_skill_index(frontline_entry.slot, skill.skill_index)
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
        target_type: SkillTargetType,
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
