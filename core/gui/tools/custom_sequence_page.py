"""Qt 版自定义操作序列录入页。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.gui.tools.custom_sequence_state import (
    TurnEditorState,
    format_action_text,
    format_noble_text,
    load_selected_sequence_name,
    load_turn_map_from_sequence,
    normalize_sequence_name,
    save_turn_map,
)
from core.shared.config_models import CustomSequenceAction


TARGET_CANCEL = object()


class TargetDialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.selected_target: int | None | object = TARGET_CANCEL
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        row = QHBoxLayout()
        for index in (1, 2, 3):
            button = QPushButton(f"从者 {index}")
            button.clicked.connect(
                lambda _checked=False, value=index: self._accept_target(value)
            )
            row.addWidget(button)
        layout.addLayout(row)
        none_button = QPushButton("None")
        none_button.clicked.connect(lambda: self._accept_target(None))
        layout.addWidget(none_button)

    def _accept_target(self, value: int | None) -> None:
        self.selected_target = value
        self.accept()


class CustomSequencePage(QWidget):
    """GUI 主程序中的自定义操作序列编辑页。"""

    def __init__(self, *, config_path: str | Path = "config/battle_config.yaml") -> None:
        super().__init__()
        self.config_path = Path(config_path)
        self.turn_map: dict[tuple[int, int], TurnEditorState] = {}
        self._current_turn_state = TurnEditorState()
        self._build_ui()
        self._load_selected_sequence()

    def window_title(self) -> str:
        return "自定义操作序列"

    def current_sequence_name(self) -> str:
        return self.sequence_name_edit.text().strip()

    def set_current_turn(self, wave: int, turn: int) -> None:
        self._store_current_turn_state()
        self.wave_spin.blockSignals(True)
        self.turn_spin.blockSignals(True)
        self.wave_spin.setValue(max(wave, 1))
        self.turn_spin.setValue(max(turn, 1))
        self.wave_spin.blockSignals(False)
        self.turn_spin.blockSignals(False)
        self._load_current_turn_state()

    def add_enemy_target_action(self, target: int) -> None:
        self._current_turn_state.actions.append(
            CustomSequenceAction(type="enemy_target", target=target)
        )
        self._refresh_lists()

    def save_sequence(self) -> None:
        self._store_current_turn_state()
        save_turn_map(
            self.config_path,
            self.current_sequence_name(),
            self.turn_map,
        )
        self.status_label.setText("已保存当前操作序列")
        self._refresh_side_summary()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        content_row = QHBoxLayout()
        content_row.setSpacing(10)
        root.addLayout(content_row, stretch=1)

        main_panel = QWidget()
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("序列文件"))
        self.sequence_name_edit = QLineEdit()
        top_row.addWidget(self.sequence_name_edit, stretch=1)
        load_button = QPushButton("加载")
        top_row.addWidget(load_button)
        main_layout.addLayout(top_row)

        turn_row = QHBoxLayout()
        turn_row.addWidget(QLabel("Wave"))
        self.wave_spin = QSpinBox()
        self.wave_spin.setMinimum(1)
        turn_row.addWidget(self.wave_spin)
        turn_row.addWidget(QLabel("Turn"))
        self.turn_spin = QSpinBox()
        self.turn_spin.setMinimum(1)
        turn_row.addWidget(self.turn_spin)
        turn_row.addStretch(1)
        main_layout.addLayout(turn_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_action_panel())
        splitter.addWidget(self._build_list_panel())
        splitter.setSizes([620, 520])
        main_layout.addWidget(splitter, stretch=1)
        content_row.addWidget(main_panel, stretch=1)

        side_panel = QFrame()
        side_panel.setObjectName("customSequenceSidePanel")
        side_panel.setFrameShape(QFrame.Shape.StyledPanel)
        side_panel.setMaximumWidth(360)
        side_panel.setMinimumWidth(300)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(10)
        side_layout.addWidget(QLabel("当前摘要"))
        self.summary_sequence_label = QLabel("序列：-")
        self.summary_turn_label = QLabel("回合：-")
        self.summary_actions_label = QLabel("动作数：0")
        self.summary_nobles_label = QLabel("宝具数：0")
        for label in (
            self.summary_sequence_label,
            self.summary_turn_label,
            self.summary_actions_label,
            self.summary_nobles_label,
        ):
            label.setWordWrap(True)
            side_layout.addWidget(label)
        self.save_button = QPushButton("保存")
        side_layout.addWidget(self.save_button)
        self.status_label = QLabel("等待编辑")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label.setWordWrap(True)
        side_layout.addWidget(self.status_label)
        side_layout.addStretch(1)
        content_row.addWidget(side_panel, stretch=0)

        load_button.clicked.connect(self._load_selected_sequence)
        self.save_button.clicked.connect(self.save_sequence)
        self.wave_spin.valueChanged.connect(self._load_current_turn_state)
        self.turn_spin.valueChanged.connect(self._load_current_turn_state)

    def _build_action_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        enemy_group = QGroupBox("敌方目标")
        enemy_layout = QHBoxLayout(enemy_group)
        for index in (1, 2, 3):
            button = QPushButton(f"敌方 {index}")
            button.clicked.connect(
                lambda _checked=False, value=index: self.add_enemy_target_action(value)
            )
            enemy_layout.addWidget(button)
        layout.addWidget(enemy_group)

        servant_group = QGroupBox("从者技能")
        servant_layout = QGridLayout(servant_group)
        for servant in (1, 2, 3):
            servant_layout.addWidget(QLabel(f"从者 {servant}"), servant - 1, 0)
            for skill in (1, 2, 3):
                button = QPushButton(f"技{skill}")
                button.clicked.connect(
                    lambda _checked=False, actor=servant, value=skill: self._add_servant_skill(actor, value)
                )
                servant_layout.addWidget(button, servant - 1, skill)
            noble_button = QPushButton("NP")
            noble_button.clicked.connect(
                lambda _checked=False, index=servant: self._add_noble(index)
            )
            servant_layout.addWidget(noble_button, servant - 1, 4)
        layout.addWidget(servant_group)

        master_group = QGroupBox("御主技能")
        master_layout = QHBoxLayout(master_group)
        for skill in (1, 2):
            button = QPushButton(f"御主 {skill}")
            button.clicked.connect(
                lambda _checked=False, value=skill: self._add_master_skill(value)
            )
            master_layout.addWidget(button)
        disabled = QPushButton("御主 3（未支持）")
        disabled.setEnabled(False)
        master_layout.addWidget(disabled)
        layout.addWidget(master_group)
        layout.addStretch(1)
        return panel

    def _build_list_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("当前回合动作"))
        self.actions_list = QListWidget()
        layout.addWidget(self.actions_list, stretch=1)
        action_buttons = QHBoxLayout()
        remove_action = QPushButton("删除动作")
        move_action_up = QPushButton("动作上移")
        move_action_down = QPushButton("动作下移")
        action_buttons.addWidget(remove_action)
        action_buttons.addWidget(move_action_up)
        action_buttons.addWidget(move_action_down)
        layout.addLayout(action_buttons)

        layout.addWidget(QLabel("当前回合宝具"))
        self.nobles_list = QListWidget()
        layout.addWidget(self.nobles_list, stretch=1)
        noble_buttons = QHBoxLayout()
        remove_noble = QPushButton("删除宝具")
        move_noble_up = QPushButton("宝具上移")
        move_noble_down = QPushButton("宝具下移")
        noble_buttons.addWidget(remove_noble)
        noble_buttons.addWidget(move_noble_up)
        noble_buttons.addWidget(move_noble_down)
        layout.addLayout(noble_buttons)

        remove_action.clicked.connect(self._remove_selected_action)
        move_action_up.clicked.connect(lambda: self._move_action(-1))
        move_action_down.clicked.connect(lambda: self._move_action(1))
        remove_noble.clicked.connect(self._remove_selected_noble)
        move_noble_up.clicked.connect(lambda: self._move_noble(-1))
        move_noble_down.clicked.connect(lambda: self._move_noble(1))
        return panel

    def _load_selected_sequence(self) -> None:
        manual_name = self.sequence_name_edit.text().strip()
        selected = manual_name or load_selected_sequence_name(self.config_path) or "default.yaml"
        selected = normalize_sequence_name(selected)
        self.sequence_name_edit.setText(selected)
        self.turn_map = load_turn_map_from_sequence(self.config_path, selected)
        self._load_current_turn_state()
        self.status_label.setText(f"已加载序列：{selected}")
        self._refresh_side_summary()

    def _current_turn_key(self) -> tuple[int, int]:
        return (self.wave_spin.value(), self.turn_spin.value())

    def _store_current_turn_state(self) -> None:
        key = self._current_turn_key()
        state = self._current_turn_state.clone()
        if state.is_empty():
            self.turn_map.pop(key, None)
        else:
            self.turn_map[key] = state

    def _load_current_turn_state(self) -> None:
        key = self._current_turn_key()
        self._current_turn_state = self.turn_map.get(key, TurnEditorState()).clone()
        self._refresh_lists()
        self._refresh_side_summary()

    def _refresh_lists(self) -> None:
        self.actions_list.clear()
        for action in self._current_turn_state.actions:
            self.actions_list.addItem(format_action_text(action))
        self.nobles_list.clear()
        for noble in self._current_turn_state.nobles:
            self.nobles_list.addItem(format_noble_text(noble))

    def _refresh_side_summary(self) -> None:
        self.summary_sequence_label.setText(f"序列：{self.current_sequence_name() or '-'}")
        self.summary_turn_label.setText(
            f"回合：Wave {self.wave_spin.value()} / Turn {self.turn_spin.value()}"
        )
        self.summary_actions_label.setText(
            f"动作数：{len(self._current_turn_state.actions)}"
        )
        self.summary_nobles_label.setText(
            f"宝具数：{len(self._current_turn_state.nobles)}"
        )

    def _ask_target(self, title: str) -> int | None | object:
        dialog = TargetDialog(title, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return TARGET_CANCEL
        return dialog.selected_target

    def _add_servant_skill(self, actor: int, skill: int) -> None:
        target = self._ask_target(f"从者 {actor} 技能 {skill} 目标")
        if target is TARGET_CANCEL:
            return
        self._current_turn_state.actions.append(
            CustomSequenceAction(
                type="servant_skill",
                actor=actor,
                skill=skill,
                target=target if target in (None, 1, 2, 3) else None,
            )
        )
        self._refresh_lists()
        self._refresh_side_summary()

    def _add_master_skill(self, skill: int) -> None:
        target = self._ask_target(f"御主技能 {skill} 目标")
        if target is TARGET_CANCEL:
            return
        self._current_turn_state.actions.append(
            CustomSequenceAction(
                type="master_skill",
                skill=skill,
                target=target if target in (None, 1, 2, 3) else None,
            )
        )
        self._refresh_lists()
        self._refresh_side_summary()

    def _add_noble(self, servant_index: int) -> None:
        self._current_turn_state.nobles.append(servant_index)
        self._refresh_lists()
        self._refresh_side_summary()

    def _remove_selected_action(self) -> None:
        row = self.actions_list.currentRow()
        if row < 0:
            return
        del self._current_turn_state.actions[row]
        self._refresh_lists()
        self._refresh_side_summary()

    def _remove_selected_noble(self) -> None:
        row = self.nobles_list.currentRow()
        if row < 0:
            return
        del self._current_turn_state.nobles[row]
        self._refresh_lists()
        self._refresh_side_summary()

    def _move_action(self, delta: int) -> None:
        row = self.actions_list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= len(self._current_turn_state.actions):
            return
        actions = self._current_turn_state.actions
        actions[row], actions[target] = actions[target], actions[row]
        self._refresh_lists()
        self.actions_list.setCurrentRow(target)
        self._refresh_side_summary()

    def _move_noble(self, delta: int) -> None:
        row = self.nobles_list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= len(self._current_turn_state.nobles):
            return
        nobles = self._current_turn_state.nobles
        nobles[row], nobles[target] = nobles[target], nobles[row]
        self._refresh_lists()
        self.nobles_list.setCurrentRow(target)
        self._refresh_side_summary()
