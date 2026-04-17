from __future__ import annotations

import argparse
import ctypes
import os
import sys
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox
from typing import Final

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = Path(__file__).resolve()
VENV_CFG_PATH = REPO_ROOT / ".venv" / "pyvenv.cfg"
SITE_PACKAGES_PATH = REPO_ROOT / ".venv" / "Lib" / "site-packages"
TARGET_PYTHON_VERSION: Final[tuple[int, int]] = (3, 12)
BOOTSTRAP_ENV: Final[str] = "LUMINA_CUSTOM_SEQUENCE_RECORDER_BOOTSTRAPPED"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "battle_config.yaml"
DEFAULT_SEQUENCE_DIR = DEFAULT_CONFIG_PATH.parent / "custom_sequences"
TARGET_DIALOG_CANCEL = object()


def _read_pyvenv_home() -> Path:
    if not VENV_CFG_PATH.exists():
        raise RuntimeError(f"missing virtual environment config: {VENV_CFG_PATH}")

    for raw_line in VENV_CFG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "home":
            return Path(value.strip())

    raise RuntimeError(f"missing 'home' entry in {VENV_CFG_PATH}")


def _build_python_path(existing: str | None) -> str:
    parts = [str(REPO_ROOT), str(SITE_PACKAGES_PATH)]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def ensure_runtime() -> None:
    if not SITE_PACKAGES_PATH.exists():
        raise RuntimeError(f"missing site-packages directory: {SITE_PACKAGES_PATH}")

    if sys.version_info[:2] != TARGET_PYTHON_VERSION:
        if os.environ.get(BOOTSTRAP_ENV) == "1":
            raise RuntimeError(
                "failed to switch to Python 3.12 for custom_sequence_recorder.py"
            )

        python_home = _read_pyvenv_home()
        python_executable = python_home / "python.exe"
        if not python_executable.exists():
            raise RuntimeError(f"missing Python executable: {python_executable}")

        env = os.environ.copy()
        env[BOOTSTRAP_ENV] = "1"
        env["PYTHONPATH"] = _build_python_path(env.get("PYTHONPATH"))
        os.execve(
            str(python_executable),
            [str(python_executable), str(SCRIPT_PATH), *sys.argv[1:]],
            env,
        )

    site_packages = str(SITE_PACKAGES_PATH)
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    if site_packages not in sys.path:
        sys.path.insert(0, site_packages)


ensure_runtime()

from core.shared.config_models import (  # noqa: E402
    CustomSequenceAction,
    CustomTurnPlan,
)
from core.shared.config_loader import (  # noqa: E402
    load_custom_sequence_turns_from_file,
    resolve_custom_sequence_path,
)


WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 980
BG_ROOT = "#11161c"
BG_PANEL = "#1a2129"
BG_BLOCK = "#121920"
FG_TEXT = "#ecf0f3"
FG_MUTED = "#8d98a5"
ACCENT = "#50c4d3"
ENEMY_COLOR = "#7ac8ff"
SERVANT_COLOR = "#59d38b"
MASTER_COLOR = "#f59f58"
NP_COLOR = "#d7b34b"
BUTTON_BG = "#2b3642"
BUTTON_ACTIVE = "#324151"


@dataclass(frozen=True)
class UiMetrics:
    scale: float
    window_width: int
    window_height: int
    sidebar_width: int
    pad_small: int
    pad_medium: int
    pad_large: int
    button_pady: int
    compact_button_pady: int
    title_font_size: int
    heading_font_size: int
    body_font_size: int
    mono_font_size: int
    nav_button_width: int
    listbox_height: int
    sidebar_list_columns: int
    status_lines: int


@dataclass(eq=True)
class TurnEditorState:
    actions: list[CustomSequenceAction] = field(default_factory=list)
    nobles: list[int] = field(default_factory=list)

    def clone(self) -> "TurnEditorState":
        return TurnEditorState(
            actions=list(self.actions),
            nobles=list(self.nobles),
        )

    def is_empty(self) -> bool:
        return not self.actions and not self.nobles


def build_ui_metrics(screen_width: int, screen_height: int) -> UiMetrics:
    scale = min(screen_width / 1920, screen_height / 1080)
    scale = max(1.0, min(scale, 1.2))
    return UiMetrics(
        scale=scale,
        window_width=min(int(WINDOW_WIDTH * scale), int(screen_width * 0.92)),
        window_height=min(int(WINDOW_HEIGHT * scale), int(screen_height * 0.92)),
        sidebar_width=int(460 * scale),
        pad_small=max(6, int(8 * scale)),
        pad_medium=max(10, int(12 * scale)),
        pad_large=max(14, int(16 * scale)),
        button_pady=max(10, int(10 * scale)),
        compact_button_pady=max(8, int(8 * scale)),
        title_font_size=max(12, int(12 * scale)),
        heading_font_size=max(11, int(11 * scale)),
        body_font_size=max(10, int(10 * scale)),
        mono_font_size=max(10, int(10 * scale)),
        nav_button_width=max(3, int(3 * scale)),
        listbox_height=max(7, int(7 * scale)),
        sidebar_list_columns=2,
        status_lines=max(4, int(4 * scale)),
    )


def step_wave_turn_together(wave: int, turn: int, delta: int) -> tuple[int, int]:
    next_wave = max(int(wave) + delta, 1)
    next_turn = max(int(turn) + delta, 1)
    return next_wave, next_turn


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


def load_turn_map(config_path: Path) -> dict[tuple[int, int], TurnEditorState]:
    selected_sequence = load_selected_sequence_name(config_path)
    if not selected_sequence:
        return {}
    return load_turn_map_from_sequence(config_path, selected_sequence)


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


def _render_action_lines(action: CustomSequenceAction) -> list[str]:
    lines = [f"        - type: {action.type}"]
    if action.actor is not None:
        lines.append(f"          actor: {action.actor}")
    if action.skill is not None:
        lines.append(f"          skill: {action.skill}")
    if action.target is None:
        lines.append("          target: null")
    else:
        lines.append(f"          target: {action.target}")
    return lines


def render_sequence_yaml(
    turn_map: dict[tuple[int, int], TurnEditorState],
) -> str:
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
                lines.extend(line[2:] for line in _render_action_lines(action))
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
        return f"servant {action.actor} skill {action.skill} -> {action.target_text}"
    return f"master skill {action.skill} -> {action.target_text}"


def format_noble_text(servant_index: int) -> str:
    return f"noble -> servant {servant_index}"


def _action_target_text(target: int | None) -> str:
    if target is None:
        return "None"
    return f"servant {target}"


CustomSequenceAction.target_text = property(  # type: ignore[attr-defined]
    lambda self: _action_target_text(self.target)
)


def enable_dpi_awareness() -> None:
    if os.name != "nt":
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class TargetSelectionDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str, *, ui: UiMetrics) -> None:
        super().__init__(parent)
        self.ui = ui
        self.result = TARGET_DIALOG_CANCEL
        self.title(title)
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close_without_selection)
        self.bind("<Escape>", lambda _event: self._close_without_selection())

        container = tk.Frame(
            self,
            bg=BG_PANEL,
            padx=self.ui.pad_large,
            pady=self.ui.pad_large,
        )
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            container,
            text=title,
            bg=BG_PANEL,
            fg=FG_TEXT,
            font=("Segoe UI", self.ui.title_font_size, "bold"),
        ).pack(fill=tk.X, pady=(0, self.ui.pad_medium))

        for index in (1, 2, 3):
            tk.Button(
                container,
                text=f"从者 {index}",
                command=lambda value=index: self._select(value),
                bg=BUTTON_BG,
                fg=FG_TEXT,
                activebackground=BUTTON_ACTIVE,
                activeforeground=FG_TEXT,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                font=("Segoe UI", self.ui.body_font_size),
                pady=self.ui.compact_button_pady,
            ).pack(fill=tk.X, pady=(0, self.ui.pad_small))

        tk.Button(
            container,
            text="None",
            command=lambda: self._select(None),
            bg="#3c4650",
            fg=FG_TEXT,
            activebackground="#46535f",
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", self.ui.body_font_size, "bold"),
            pady=self.ui.button_pady,
        ).pack(fill=tk.X, pady=(self.ui.pad_small, 0))

        self.update_idletasks()
        self._center_over_parent(parent)

    def _center_over_parent(self, parent: tk.Misc) -> None:
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        width = self.winfo_width()
        height = self.winfo_height()
        pos_x = parent_x + max((parent_width - width) // 2, 0)
        pos_y = parent_y + max((parent_height - height) // 2, 0)
        self.geometry(f"+{pos_x}+{pos_y}")

    def _select(self, value: int | None) -> None:
        self.result = value
        self.destroy()

    def _close_without_selection(self) -> None:
        self.result = TARGET_DIALOG_CANCEL
        self.destroy()


def ask_target(parent: tk.Misc, title: str) -> object | int | None:
    ui = getattr(parent, "_lumina_ui_metrics", build_ui_metrics(1920, 1080))
    dialog = TargetSelectionDialog(parent, title, ui=ui)
    parent.wait_window(dialog)
    return dialog.result


class CustomSequenceRecorderApp:
    def __init__(self, root: tk.Tk, config_path: Path) -> None:
        self.root = root
        self.config_path = config_path
        self.ui = build_ui_metrics(root.winfo_screenwidth(), root.winfo_screenheight())
        self.turn_map: dict[tuple[int, int], TurnEditorState] = {}
        self.current_key = (1, 1)
        self.current_state = TurnEditorState()
        self.wave_var = tk.IntVar(value=1)
        self.turn_var = tk.IntVar(value=1)
        self.sequence_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="准备就绪")
        self.config_var = tk.StringVar(value=str(config_path))
        self._building_ui = True

        self.root.title("Lumina Custom Sequence Recorder")
        self.root.configure(bg=BG_ROOT)
        self.root._lumina_ui_metrics = self.ui  # type: ignore[attr-defined]
        self.root.geometry(self._build_geometry())
        self.root.minsize(
            max(1480, int(1480 * self.ui.scale)),
            max(900, int(900 * self.ui.scale)),
        )

        self._build_layout()
        self._bind_shortcuts()
        self._load_config()
        self._building_ui = False
        self._load_turn(self.current_key)

    def _build_geometry(self) -> str:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        pos_x = max((screen_width - self.ui.window_width) // 2, 0)
        pos_y = max((screen_height - self.ui.window_height) // 2, 0)
        return f"{self.ui.window_width}x{self.ui.window_height}+{pos_x}+{pos_y}"

    def _build_layout(self) -> None:
        outer = tk.Frame(self.root, bg=BG_ROOT)
        outer.pack(
            fill=tk.BOTH,
            expand=True,
            padx=self.ui.pad_medium,
            pady=self.ui.pad_medium,
        )

        left = tk.Frame(outer, bg=BG_ROOT)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = tk.Frame(outer, bg=BG_PANEL, width=self.ui.sidebar_width)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        self._build_board(left)
        self._build_sidebar(right)

    def _build_board(self, parent: tk.Widget) -> None:
        board = tk.Frame(parent, bg=BG_ROOT)
        board.pack(fill=tk.BOTH, expand=True)
        board.columnconfigure(0, weight=1)
        board.columnconfigure(1, weight=1)
        board.columnconfigure(2, weight=1)
        board.columnconfigure(3, weight=1)
        board.rowconfigure(0, weight=1)
        board.rowconfigure(1, weight=2)

        enemy_title = tk.Label(
            board,
            text="敌方目标",
            bg=BG_ROOT,
            fg=FG_MUTED,
            font=("Segoe UI", self.ui.heading_font_size, "bold"),
        )
        enemy_title.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            padx=(self.ui.pad_small, 0),
            pady=(0, self.ui.pad_small),
        )

        for index in (1, 2, 3):
            self._create_enemy_panel(board, index).grid(
                row=0,
                column=index - 1,
                sticky="nsew",
                padx=self.ui.pad_small,
                pady=(int(32 * self.ui.scale), self.ui.pad_medium),
            )

        servant_title = tk.Label(
            board,
            text="前排从者",
            bg=BG_ROOT,
            fg=FG_MUTED,
            font=("Segoe UI", self.ui.heading_font_size, "bold"),
        )
        servant_title.grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="w",
            padx=(self.ui.pad_small, 0),
            pady=(0, self.ui.pad_small),
        )

        for actor in (1, 2, 3):
            self._create_servant_panel(board, actor).grid(
                row=1,
                column=actor - 1,
                sticky="nsew",
                padx=self.ui.pad_small,
                pady=(int(30 * self.ui.scale), self.ui.pad_small),
            )

        master_panel = self._create_master_panel(board)
        master_panel.grid(
            row=0,
            column=3,
            rowspan=2,
            sticky="nsew",
            padx=(self.ui.pad_medium, self.ui.pad_small),
            pady=self.ui.pad_small,
        )

    def _create_enemy_panel(self, parent: tk.Widget, index: int) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG_BLOCK, highlightthickness=2, highlightbackground=ENEMY_COLOR)
        tk.Label(
            frame,
            text=f"敌人 {index}",
            bg=BG_BLOCK,
            fg=ENEMY_COLOR,
            font=("Segoe UI", self.ui.title_font_size, "bold"),
        ).pack(
            fill=tk.X,
            padx=self.ui.pad_medium,
            pady=(self.ui.pad_medium, self.ui.pad_small),
        )
        tk.Button(
            frame,
            text=f"选择敌方 {index}",
            command=lambda value=index: self._append_enemy_target(value),
            bg=BUTTON_BG,
            fg=FG_TEXT,
            activebackground=BUTTON_ACTIVE,
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", self.ui.body_font_size),
            pady=self.ui.button_pady,
        ).pack(
            fill=tk.X,
            padx=self.ui.pad_medium,
            pady=(0, self.ui.pad_medium),
        )
        return frame

    def _create_servant_panel(self, parent: tk.Widget, actor: int) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG_BLOCK, highlightthickness=2, highlightbackground=SERVANT_COLOR)
        tk.Label(
            frame,
            text=f"从者 {actor}",
            bg=BG_BLOCK,
            fg=SERVANT_COLOR,
            font=("Segoe UI", self.ui.title_font_size, "bold"),
        ).pack(
            fill=tk.X,
            padx=self.ui.pad_medium,
            pady=(self.ui.pad_medium, self.ui.pad_small),
        )
        for skill in (1, 2, 3):
            tk.Button(
                frame,
                text=f"技能 {skill}",
                command=lambda a=actor, s=skill: self._append_servant_skill(a, s),
                bg=BUTTON_BG,
                fg=FG_TEXT,
                activebackground=BUTTON_ACTIVE,
                activeforeground=FG_TEXT,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                font=("Segoe UI", self.ui.body_font_size),
                pady=self.ui.button_pady,
            ).pack(
                fill=tk.X,
                padx=self.ui.pad_medium,
                pady=(0, self.ui.pad_small),
            )
        tk.Button(
            frame,
            text="NP",
            command=lambda value=actor: self._append_noble(value),
            bg="#3b3d22",
            fg=FG_TEXT,
            activebackground="#50502e",
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", self.ui.body_font_size, "bold"),
            pady=self.ui.button_pady,
        ).pack(
            fill=tk.X,
            padx=self.ui.pad_medium,
            pady=(max(4, int(4 * self.ui.scale)), self.ui.pad_medium),
        )
        return frame

    def _create_master_panel(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG_BLOCK, highlightthickness=2, highlightbackground=MASTER_COLOR)
        tk.Label(
            frame,
            text="御主技能",
            bg=BG_BLOCK,
            fg=MASTER_COLOR,
            font=("Segoe UI", self.ui.title_font_size, "bold"),
        ).pack(
            fill=tk.X,
            padx=self.ui.pad_medium,
            pady=(self.ui.pad_medium, self.ui.pad_small),
        )
        for skill in (1, 2):
            tk.Button(
                frame,
                text=f"御主技能 {skill}",
                command=lambda s=skill: self._append_master_skill(s),
                bg=BUTTON_BG,
                fg=FG_TEXT,
                activebackground=BUTTON_ACTIVE,
                activeforeground=FG_TEXT,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                font=("Segoe UI", self.ui.body_font_size),
                pady=self.ui.button_pady,
            ).pack(
                fill=tk.X,
                padx=self.ui.pad_medium,
                pady=(0, self.ui.pad_small),
            )
        tk.Button(
            frame,
            text="御主技能 3（未支持）",
            state=tk.DISABLED,
            bg="#3d2d2d",
            fg="#b89b9b",
            disabledforeground="#b89b9b",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", self.ui.body_font_size),
            pady=self.ui.button_pady,
        ).pack(
            fill=tk.X,
            padx=self.ui.pad_medium,
            pady=(0, self.ui.pad_medium),
        )
        return frame

    def _build_sidebar(self, parent: tk.Widget) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(3, weight=1)

        header = tk.Frame(parent, bg=BG_PANEL)
        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=self.ui.pad_large,
            pady=(self.ui.pad_large, self.ui.pad_medium),
        )
        header.grid_columnconfigure(0, weight=1)
        tk.Label(
            header,
            text="配置文件",
            bg=BG_PANEL,
            fg=FG_MUTED,
            anchor="w",
            font=("Segoe UI", self.ui.body_font_size),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))
        tk.Label(
            header,
            textvariable=self.config_var,
            bg=BG_PANEL,
            fg=FG_TEXT,
            anchor="w",
            justify="left",
            wraplength=self.ui.sidebar_width - (self.ui.pad_large * 2),
            font=("Consolas", self.ui.mono_font_size),
        ).grid(row=1, column=0, sticky="ew", pady=(0, self.ui.pad_medium))
        tk.Label(
            header,
            text="序列文件",
            bg=BG_PANEL,
            fg=FG_MUTED,
            anchor="w",
            font=("Segoe UI", self.ui.body_font_size),
        ).grid(row=2, column=0, sticky="ew", pady=(0, 4))

        sequence_row = tk.Frame(header, bg=BG_PANEL)
        sequence_row.grid(row=3, column=0, sticky="ew")
        sequence_row.columnconfigure(0, weight=1)

        sequence_entry = tk.Entry(
            sequence_row,
            textvariable=self.sequence_var,
            bg=BG_BLOCK,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief=tk.FLAT,
            font=("Consolas", self.ui.mono_font_size),
        )
        sequence_entry.grid(
            row=0,
            column=0,
            sticky="we",
            padx=(0, self.ui.pad_small),
            ipady=max(4, int(4 * self.ui.scale)),
        )
        sequence_entry.bind("<Return>", lambda _event: self._load_sequence_from_entry())

        tk.Button(
            sequence_row,
            text="载入",
            command=self._load_sequence_from_entry,
            bg=BUTTON_BG,
            fg=FG_TEXT,
            activebackground=BUTTON_ACTIVE,
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", self.ui.body_font_size),
            pady=self.ui.compact_button_pady,
        ).grid(row=0, column=1, sticky="e")

        nav = tk.Frame(parent, bg=BG_PANEL)
        nav.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=self.ui.pad_large,
            pady=(0, self.ui.pad_medium),
        )
        self._build_counter_row(nav, "Wave", self.wave_var, self._step_wave, row=0)
        self._build_counter_row(nav, "Turn", self.turn_var, self._step_turn, row=1)

        list_area = tk.Frame(parent, bg=BG_PANEL)
        list_area.grid(
            row=3,
            column=0,
            sticky="nsew",
            padx=self.ui.pad_large,
            pady=(0, self.ui.pad_medium),
        )
        for column in range(self.ui.sidebar_list_columns):
            list_area.grid_columnconfigure(column, weight=1)
        list_area.grid_rowconfigure(0, weight=1)

        self._build_list_section(
            parent=list_area,
            title="当前回合 Actions",
            list_attr="actions_listbox",
            move_up=self._move_selected_action_up,
            move_down=self._move_selected_action_down,
            delete=self._delete_selected_action,
            column=0,
        )
        self._build_list_section(
            parent=list_area,
            title="当前回合 Nobles",
            list_attr="nobles_listbox",
            move_up=self._move_selected_noble_up,
            move_down=self._move_selected_noble_down,
            delete=self._delete_selected_noble,
            column=1,
        )

        footer = tk.Frame(parent, bg=BG_PANEL)
        footer.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=self.ui.pad_large,
            pady=(0, self.ui.pad_large),
        )
        tk.Button(
            footer,
            text="保存当前序列",
            command=self._save_to_config,
            bg="#2f5f43",
            fg=FG_TEXT,
            activebackground="#3a7653",
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", self.ui.body_font_size, "bold"),
            pady=max(12, int(12 * self.ui.scale)),
        ).pack(
            fill=tk.X,
            pady=(0, self.ui.pad_medium),
        )

        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=BG_PANEL,
            fg=ACCENT,
            anchor="nw",
            justify="left",
            wraplength=self.ui.sidebar_width - (self.ui.pad_large * 2),
            font=("Segoe UI", self.ui.body_font_size),
            height=self.ui.status_lines,
        ).pack(fill=tk.X)

    def _build_list_section(
        self,
        *,
        parent: tk.Widget,
        title: str,
        list_attr: str,
        move_up,
        move_down,
        delete,
        column: int,
    ) -> None:
        section = tk.Frame(parent, bg=BG_PANEL)
        section.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0, self.ui.pad_small) if column == 0 else (self.ui.pad_small, 0),
        )
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(1, weight=1)

        tk.Label(
            section,
            text=title,
            bg=BG_PANEL,
            fg=FG_MUTED,
            anchor="w",
            font=("Segoe UI", self.ui.body_font_size),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 6))
        listbox = tk.Listbox(
            section,
            bg=BG_BLOCK,
            fg=FG_TEXT,
            selectbackground="#385c74",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground="#26313d",
            font=("Consolas", self.ui.mono_font_size),
            height=self.ui.listbox_height,
        )
        listbox.grid(row=1, column=0, sticky="nsew", pady=(0, self.ui.pad_small))
        setattr(self, list_attr, listbox)

        button_row = tk.Frame(section, bg=BG_PANEL)
        button_row.grid(row=2, column=0, sticky="ew")
        for text, command in (("上移", move_up), ("下移", move_down), ("删除", delete)):
            tk.Button(
                button_row,
                text=text,
                command=command,
                bg=BUTTON_BG,
                fg=FG_TEXT,
                activebackground=BUTTON_ACTIVE,
                activeforeground=FG_TEXT,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                font=("Segoe UI", self.ui.body_font_size),
                pady=self.ui.compact_button_pady,
            ).pack(
                side=tk.LEFT,
                fill=tk.X,
                expand=True,
                padx=(0, self.ui.pad_small),
            )
        button_row.winfo_children()[-1].pack_configure(padx=(0, 0))

    def _build_counter_row(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.IntVar,
        step_command,
        *,
        row: int,
    ) -> None:
        parent.columnconfigure(1, weight=1)
        tk.Label(
            parent,
            text=label,
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", self.ui.body_font_size, "bold"),
        ).grid(
            row=row,
            column=0,
            sticky="w",
            pady=(0, self.ui.pad_small),
        )

        controls = tk.Frame(parent, bg=BG_PANEL)
        controls.grid(
            row=row,
            column=1,
            sticky="we",
            pady=(0, self.ui.pad_small),
        )
        controls.columnconfigure(1, weight=1)

        tk.Button(
            controls,
            text="-",
            command=lambda: step_command(-1),
            bg=BUTTON_BG,
            fg=FG_TEXT,
            activebackground=BUTTON_ACTIVE,
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", self.ui.body_font_size, "bold"),
            width=self.ui.nav_button_width,
            pady=self.ui.compact_button_pady,
        ).grid(row=0, column=0, sticky="w", padx=(0, self.ui.pad_small))

        entry = tk.Entry(
            controls,
            textvariable=variable,
            justify="center",
            bg=BG_BLOCK,
            fg=FG_TEXT,
            insertbackground=FG_TEXT,
            relief=tk.FLAT,
            font=("Consolas", max(self.ui.mono_font_size + 2, 12)),
        )
        entry.grid(row=0, column=1, sticky="we", ipady=max(6, int(6 * self.ui.scale)))
        entry.bind("<FocusOut>", lambda _event: self._on_turn_coordinate_changed())
        entry.bind("<Return>", lambda _event: self._on_turn_coordinate_changed())

        tk.Button(
            controls,
            text="+",
            command=lambda: step_command(1),
            bg=BUTTON_BG,
            fg=FG_TEXT,
            activebackground=BUTTON_ACTIVE,
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", self.ui.body_font_size, "bold"),
            width=self.ui.nav_button_width,
            pady=self.ui.compact_button_pady,
        ).grid(row=0, column=2, sticky="e", padx=(self.ui.pad_small, 0))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-s>", lambda _event: self._save_to_config())

    def _load_config(self) -> None:
        try:
            selected_sequence = load_selected_sequence_name(self.config_path)
        except Exception as exc:
            messagebox.showerror("读取失败", f"无法读取配置文件：\n{exc}")
            selected_sequence = ""
        self.sequence_var.set(selected_sequence)
        try:
            self.turn_map = (
                load_turn_map_from_sequence(self.config_path, selected_sequence)
                if selected_sequence
                else {}
            )
        except Exception as exc:
            messagebox.showerror("读取失败", f"无法读取序列文件：\n{exc}")
            self.turn_map = {}
        first_key = sorted(self.turn_map)[0] if self.turn_map else (1, 1)
        self.current_key = first_key
        self.wave_var.set(first_key[0])
        self.turn_var.set(first_key[1])

    def _current_sequence_name(self) -> str | None:
        raw_name = self.sequence_var.get().strip()
        if not raw_name:
            messagebox.showerror("缺少序列文件", "请先填写序列文件名。")
            self.status_var.set("未填写序列文件名")
            return None
        try:
            normalized_name = normalize_sequence_name(raw_name)
        except Exception as exc:
            messagebox.showerror("序列文件名无效", str(exc))
            self.status_var.set("序列文件名无效")
            return None
        self.sequence_var.set(normalized_name)
        return normalized_name

    def _load_sequence_from_entry(self) -> None:
        if self._building_ui:
            return
        sequence_name = self._current_sequence_name()
        if sequence_name is None:
            return
        self._store_current_turn()
        try:
            self.turn_map = load_turn_map_from_sequence(self.config_path, sequence_name)
        except Exception as exc:
            messagebox.showerror("读取失败", f"无法读取序列文件：\n{exc}")
            self.status_var.set("读取序列文件失败")
            return
        first_key = sorted(self.turn_map)[0] if self.turn_map else (1, 1)
        self.wave_var.set(first_key[0])
        self.turn_var.set(first_key[1])
        self._load_turn(first_key)
        if self.turn_map:
            self.status_var.set(f"已载入序列 {sequence_name}")
        else:
            self.status_var.set(f"序列 {sequence_name} 不存在或为空，当前按新序列编辑")

    def _load_turn(self, key: tuple[int, int]) -> None:
        self.current_key = key
        state = self.turn_map.get(key)
        self.current_state = state.clone() if state is not None else TurnEditorState()
        self._refresh_lists()
        self.status_var.set(f"当前编辑 wave={key[0]} turn={key[1]}")

    def _store_current_turn(self) -> None:
        if self.current_state.is_empty():
            self.turn_map.pop(self.current_key, None)
            return
        self.turn_map[self.current_key] = self.current_state.clone()

    def _refresh_lists(self) -> None:
        self.actions_listbox.delete(0, tk.END)
        for action in self.current_state.actions:
            self.actions_listbox.insert(tk.END, format_action_text(action))
        self.nobles_listbox.delete(0, tk.END)
        for noble in self.current_state.nobles:
            self.nobles_listbox.insert(tk.END, format_noble_text(noble))

    def _on_turn_coordinate_changed(self) -> None:
        if self._building_ui:
            return
        try:
            key = (max(int(self.wave_var.get()), 1), max(int(self.turn_var.get()), 1))
        except tk.TclError:
            return
        if key == self.current_key:
            return
        self._store_current_turn()
        self._load_turn(key)

    def _step_wave(self, delta: int) -> None:
        self._store_current_turn()
        wave, turn = step_wave_turn_together(
            int(self.wave_var.get()),
            int(self.turn_var.get()),
            delta,
        )
        self.wave_var.set(wave)
        self.turn_var.set(turn)
        self._load_turn((wave, turn))

    def _step_turn(self, delta: int) -> None:
        self._store_current_turn()
        wave = max(int(self.wave_var.get()), 1)
        turn = max(int(self.turn_var.get()) + delta, 1)
        self.wave_var.set(wave)
        self.turn_var.set(turn)
        self._load_turn((wave, turn))

    def _append_enemy_target(self, target: int) -> None:
        self.current_state.actions.append(
            CustomSequenceAction(type="enemy_target", target=target)
        )
        self._refresh_lists()
        self.status_var.set(f"已追加 enemy_target -> {target}")

    def _append_servant_skill(self, actor: int, skill: int) -> None:
        target = ask_target(self.root, f"从者 {actor} 技能 {skill} 选择目标")
        if target is TARGET_DIALOG_CANCEL:
            return
        self.current_state.actions.append(
            CustomSequenceAction(
                type="servant_skill",
                actor=actor,
                skill=skill,
                target=target,
            )
        )
        self._refresh_lists()
        self.status_var.set(f"已追加 servant {actor} skill {skill}")

    def _append_master_skill(self, skill: int) -> None:
        target = ask_target(self.root, f"御主技能 {skill} 选择目标")
        if target is TARGET_DIALOG_CANCEL:
            return
        self.current_state.actions.append(
            CustomSequenceAction(
                type="master_skill",
                skill=skill,
                target=target,
            )
        )
        self._refresh_lists()
        self.status_var.set(f"已追加 master skill {skill}")

    def _append_noble(self, servant_index: int) -> None:
        if servant_index in self.current_state.nobles:
            self.status_var.set(f"{servant_index} 号宝具已在当前回合顺序中")
            return
        self.current_state.nobles.append(servant_index)
        self._refresh_lists()
        self.status_var.set(f"已追加 noble -> servant {servant_index}")

    def _move_selected(self, items: list, listbox: tk.Listbox, delta: int) -> bool:
        selection = listbox.curselection()
        if not selection:
            return False
        index = selection[0]
        target = index + delta
        if target < 0 or target >= len(items):
            return False
        items[index], items[target] = items[target], items[index]
        self._refresh_lists()
        listbox.selection_set(target)
        return True

    def _delete_selected(self, items: list, listbox: tk.Listbox) -> bool:
        selection = listbox.curselection()
        if not selection:
            return False
        del items[selection[0]]
        self._refresh_lists()
        return True

    def _move_selected_action_up(self) -> None:
        if self._move_selected(self.current_state.actions, self.actions_listbox, -1):
            self.status_var.set("已上移动作")

    def _move_selected_action_down(self) -> None:
        if self._move_selected(self.current_state.actions, self.actions_listbox, 1):
            self.status_var.set("已下移动作")

    def _delete_selected_action(self) -> None:
        if self._delete_selected(self.current_state.actions, self.actions_listbox):
            self.status_var.set("已删除动作")

    def _move_selected_noble_up(self) -> None:
        if self._move_selected(self.current_state.nobles, self.nobles_listbox, -1):
            self.status_var.set("已上移宝具顺序")

    def _move_selected_noble_down(self) -> None:
        if self._move_selected(self.current_state.nobles, self.nobles_listbox, 1):
            self.status_var.set("已下移宝具顺序")

    def _delete_selected_noble(self) -> None:
        if self._delete_selected(self.current_state.nobles, self.nobles_listbox):
            self.status_var.set("已删除宝具顺序")

    def _save_to_config(self) -> None:
        self._store_current_turn()
        sequence_name = self._current_sequence_name()
        if sequence_name is None:
            return
        try:
            save_turn_map(self.config_path, sequence_name, self.turn_map)
        except Exception as exc:
            messagebox.showerror("保存失败", f"写回配置文件失败：\n{exc}")
            self.status_var.set("保存失败")
            return
        self.status_var.set(f"已保存到 {sequence_name}，并更新当前加载项")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lumina 自定义操作序列 GUI 录入器")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="要读取并回写的 battle_config.yaml 路径",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    enable_dpi_awareness()
    root = tk.Tk()
    CustomSequenceRecorderApp(root, Path(args.config))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
