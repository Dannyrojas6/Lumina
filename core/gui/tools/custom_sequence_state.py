"""自定义操作序列编辑的纯数据与读写函数。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from core.shared.config_loader import (
    load_custom_sequence_turns_from_file,
    resolve_custom_sequence_path,
)
from core.shared.config_models import CustomSequenceAction, CustomTurnPlan


@dataclass(eq=True)
class TurnEditorState:
    actions: list[CustomSequenceAction] = field(default_factory=list)
    nobles: list[int] = field(default_factory=list)

    def clone(self) -> "TurnEditorState":
        return TurnEditorState(actions=list(self.actions), nobles=list(self.nobles))

    def is_empty(self) -> bool:
        return not self.actions and not self.nobles


def normalize_sequence_name(sequence_name: str) -> str:
    normalized = str(sequence_name).strip()
    if not normalized:
        raise ValueError("sequence name must not be empty")
    path = Path(normalized)
    if path.suffix.lower() != ".yaml":
        path = path.with_suffix(".yaml")
    return path.as_posix()


def load_selected_sequence_name(config_path: Path) -> str:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return ""
    raw = data.get("custom_sequence_battle", {})
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("sequence", "")).strip()


def load_turn_map_from_sequence(
    config_path: Path,
    sequence_name: str,
) -> dict[tuple[int, int], TurnEditorState]:
    turn_map: dict[tuple[int, int], TurnEditorState] = {}
    normalized_name = normalize_sequence_name(sequence_name)
    sequence_path = resolve_custom_sequence_path(config_path, normalized_name)
    if not sequence_path.exists():
        return turn_map
    for plan in load_custom_sequence_turns_from_file(config_path, normalized_name):
        turn_map[(plan.wave, plan.turn)] = TurnEditorState(
            actions=list(plan.actions),
            nobles=list(plan.nobles),
        )
    return turn_map


def collect_serializable_turns(
    turn_map: dict[tuple[int, int], TurnEditorState],
) -> list[CustomTurnPlan]:
    turns: list[CustomTurnPlan] = []
    for (wave, turn), state in sorted(turn_map.items()):
        if state.is_empty():
            continue
        turns.append(
            CustomTurnPlan(
                wave=wave,
                turn=turn,
                actions=list(state.actions),
                nobles=list(state.nobles),
            )
        )
    return turns


def render_sequence_yaml(turn_map: dict[tuple[int, int], TurnEditorState]) -> str:
    turns = collect_serializable_turns(turn_map)
    if not turns:
        return "turns: []"
    lines = ["turns:"]
    for plan in turns:
        lines.append(f"  - wave: {plan.wave}")
        lines.append(f"    turn: {plan.turn}")
        if plan.actions:
            lines.append("    actions:")
            for action in plan.actions:
                lines.append(f"      - type: {action.type}")
                if action.actor is not None:
                    lines.append(f"        actor: {action.actor}")
                if action.skill is not None:
                    lines.append(f"        skill: {action.skill}")
                if action.target is None:
                    lines.append("        target: null")
                else:
                    lines.append(f"        target: {action.target}")
        else:
            lines.append("    actions: []")
        if plan.nobles:
            joined = ", ".join(str(value) for value in plan.nobles)
            lines.append(f"    nobles: [{joined}]")
        else:
            lines.append("    nobles: []")
    return "\n".join(lines)


def render_custom_sequence_selector_block(sequence_name: str) -> str:
    if not sequence_name:
        return 'custom_sequence_battle:\n  sequence: ""'
    return f"custom_sequence_battle:\n  sequence: {sequence_name}"


def replace_custom_sequence_selector_block(
    config_text: str,
    replacement_block: str,
) -> str:
    newline = "\r\n" if "\r\n" in config_text else "\n"
    lines = config_text.splitlines()
    replacement_lines = replacement_block.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("custom_sequence_battle:"):
            start = index
            break
    if start is not None:
        end = start + 1
        while end < len(lines):
            line = lines[end]
            if line.startswith("#"):
                break
            if line and not line.startswith((" ", "\t")):
                break
            end += 1
        updated_lines = lines[:start] + replacement_lines + lines[end:]
        return newline.join(updated_lines) + newline
    insert_at = None
    for index, line in enumerate(lines):
        if line.startswith("skill_sequence:"):
            insert_at = index
            break
    if insert_at is None:
        insert_at = len(lines)
    prefix = list(lines[:insert_at])
    suffix = list(lines[insert_at:])
    if prefix and prefix[-1].strip():
        prefix.append("")
    updated_lines = prefix + replacement_lines
    if suffix:
        if suffix[0].strip():
            updated_lines.append("")
        updated_lines.extend(suffix)
    return newline.join(updated_lines) + newline


def save_turn_map(
    config_path: Path,
    sequence_name: str,
    turn_map: dict[tuple[int, int], TurnEditorState],
) -> None:
    normalized_name = normalize_sequence_name(sequence_name)
    original_text = config_path.read_text(encoding="utf-8")
    sequence_path = resolve_custom_sequence_path(config_path, normalized_name)
    sequence_path.parent.mkdir(parents=True, exist_ok=True)
    sequence_path.write_text(render_sequence_yaml(turn_map) + "\n", encoding="utf-8")
    replacement_block = render_custom_sequence_selector_block(normalized_name)
    updated_text = replace_custom_sequence_selector_block(
        original_text,
        replacement_block,
    )
    config_path.write_text(updated_text, encoding="utf-8")


def format_action_text(action: CustomSequenceAction) -> str:
    if action.type == "enemy_target":
        return f"enemy_target -> {action.target}"
    if action.type == "servant_skill":
        target_text = "None" if action.target is None else f"servant {action.target}"
        return f"servant {action.actor} skill {action.skill} -> {target_text}"
    target_text = "None" if action.target is None else f"servant {action.target}"
    return f"master skill {action.skill} -> {target_text}"


def format_noble_text(servant_index: int) -> str:
    return f"noble -> servant {servant_index}"
