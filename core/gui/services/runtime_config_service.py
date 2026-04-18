"""运行页可编辑配置的读取与回写。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml


@dataclass(frozen=True)
class RuntimeEditableConfig:
    battle_mode: Literal["main", "custom_sequence"]
    smart_battle_enabled: bool
    continue_battle: bool
    log_level: Literal["DEBUG", "INFO", "WARNING"]


def load_runtime_editable_config(
    config_path: str | Path = "config/battle_config.yaml",
) -> RuntimeEditableConfig:
    path = Path(config_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise TypeError("battle_config.yaml must be a mapping")

    battle_mode = str(data.get("battle_mode", "main")).strip().lower()
    if battle_mode not in {"main", "custom_sequence"}:
        battle_mode = "main"

    log_level = str(data.get("log_level", "INFO")).strip().upper()
    if log_level not in {"DEBUG", "INFO", "WARNING"}:
        log_level = "INFO"

    smart_battle = data.get("smart_battle", {})
    smart_enabled = False
    if isinstance(smart_battle, dict):
        smart_enabled = bool(smart_battle.get("enabled", False))

    return RuntimeEditableConfig(
        battle_mode=battle_mode,  # type: ignore[arg-type]
        smart_battle_enabled=smart_enabled,
        continue_battle=bool(data.get("continue_battle", True)),
        log_level=log_level,  # type: ignore[arg-type]
    )


def save_runtime_editable_config(
    config_path: str | Path,
    config: RuntimeEditableConfig,
) -> None:
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")
    updated = text
    updated = _replace_top_level_scalar(updated, "battle_mode", config.battle_mode)
    updated = _replace_top_level_scalar(
        updated,
        "continue_battle",
        _format_bool(config.continue_battle),
    )
    updated = _replace_top_level_scalar(updated, "log_level", config.log_level)
    updated = _replace_smart_battle_enabled(updated, config.smart_battle_enabled)
    path.write_text(updated, encoding="utf-8")


def _replace_top_level_scalar(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith(f"{key}:"):
            continue
        if line != stripped:
            continue
        comment = _extract_inline_comment(line)
        lines[index] = f"{key}: {value}{comment}"
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    lines.append(f"{key}: {value}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _replace_smart_battle_enabled(text: str, enabled: bool) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("smart_battle:"):
            block_end = index + 1
            while block_end < len(lines):
                current = lines[block_end]
                if current and not current.startswith(" "):
                    break
                block_end += 1
            for child_index in range(index + 1, block_end):
                stripped = lines[child_index].strip()
                if not stripped.startswith("enabled:"):
                    continue
                comment = _extract_inline_comment(lines[child_index])
                lines[child_index] = f"  enabled: {_format_bool(enabled)}{comment}"
                return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
            lines.insert(index + 1, f"  enabled: {_format_bool(enabled)}")
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    if lines and lines[-1].strip():
        lines.append("")
    lines.append("smart_battle:")
    lines.append(f"  enabled: {_format_bool(enabled)}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _extract_inline_comment(line: str) -> str:
    if "#" not in line:
        return ""
    comment_index = line.index("#")
    return line[comment_index - 1 :] if comment_index > 0 and line[comment_index - 1] == " " else line[comment_index:]
