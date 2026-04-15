"""普通指令卡识别的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CommandCardInfo:
    """描述单张普通指令卡的归属和颜色。"""

    index: int
    owner: str | None
    color: str | None


@dataclass(frozen=True)
class CommandCardScore:
    """描述单张卡对单个从者的最终分数。"""

    servant_name: str
    score: float
    route1_score: float = 0.0
    route2_score: float = 0.0
    valid_part_count: int = 0
    visible_weight_sum: float = 0.0
    part_scores: list["CommandCardPartScore"] = field(default_factory=list)


@dataclass(frozen=True)
class CommandCardPartScore:
    """描述单张卡某个局部区域对单个从者的评分依据。"""

    part_name: str
    score: float
    route1_score: float
    route2_score: float
    gray_score: float
    edge_score: float
    visible_ratio: float
    texture_score: float
    weight: float
    bbox_local: tuple[int, int, int, int] | None = None
    bbox_abs: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class CommandCardTrace:
    """描述单张普通卡的完整判断依据。"""

    index: int
    owner: str | None
    color: str | None
    score: float
    margin: float
    support_badge: bool
    low_confidence: bool
    scores: list[CommandCardScore] = field(default_factory=list)
    crop_region_abs: tuple[int, int, int, int] | None = None
    mask_rects_abs: list[tuple[int, int, int, int]] = field(default_factory=list)


@dataclass(frozen=True)
class CommandCardAssignmentCandidate:
    """描述整手五张卡的一组候选归属。"""

    owners_by_index: dict[int, str | None]
    score: float
    margin_from_best: float = 0.0


@dataclass(frozen=True)
class CommandCardPrediction:
    """描述一次五张普通卡识别的完整结果。"""

    frontline_servants: list[str]
    support_attacker: str | None
    traces: list[CommandCardTrace]
    min_score: float
    min_margin: float
    joint_score: float = 0.0
    joint_margin: float = 0.0
    joint_low_confidence: bool = False
    assignment_candidates: list[CommandCardAssignmentCandidate] = field(
        default_factory=list
    )

    @property
    def owners(self) -> dict[int, str | None]:
        return {trace.index: trace.owner for trace in self.traces}

    @property
    def cards(self) -> list[CommandCardInfo]:
        return [
            CommandCardInfo(
                index=trace.index,
                owner=trace.owner,
                color=trace.color,
            )
            for trace in self.traces
        ]

    @property
    def has_low_confidence(self) -> bool:
        return any(trace.low_confidence for trace in self.traces) or self.joint_low_confidence

    @property
    def low_confidence_traces(self) -> list[CommandCardTrace]:
        return [trace for trace in self.traces if trace.low_confidence]


@dataclass(frozen=True)
class CommandCardSample:
    """描述一张普通卡样本的人工真值。"""

    image: str
    frontline: list[str]
    support_attacker: str | None
    owners: list[str | None]
    note: str = ""
    occlusion_level: str = ""
    hard_negative_tags: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def image_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "test_image" / "fight" / self.image

    @property
    def owners_by_index(self) -> dict[int, str | None]:
        return {
            index + 1: owner
            for index, owner in enumerate(self.owners)
        }
