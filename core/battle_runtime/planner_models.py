"""智能战斗判断层数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

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
