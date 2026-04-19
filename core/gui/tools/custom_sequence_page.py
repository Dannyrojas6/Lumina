"""Qt 版自定义操作序列录入页。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        label = QLabel(title)
        label.setWordWrap(True)
        layout.addWidget(label)
        row = QHBoxLayout()
        row.setSpacing(6)
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
        self.wave_spin.setValue(max(min(wave, 3), 1))
        self.turn_spin.setValue(max(turn, 1))
        self.wave_spin.blockSignals(False)
        self.turn_spin.blockSignals(False)
        self._sync_wave_buttons()
        self._load_current_turn_state()

    def add_enemy_target_action(self, target: int) -> None:
        self._current_turn_state.actions.append(
            CustomSequenceAction(type="enemy_target", target=target)
        )
        self._refresh_lists()
        self._refresh_side_summary()

    def save_sequence(self) -> None:
        self._store_current_turn_state()
        save_turn_map(
            self.config_path,
            self.current_sequence_name(),
            self.turn_map,
        )
        self.status_label.setText("已保存当前操作序列")
        self._refresh_side_summary()
        self._refresh_history_and_overview()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        left_panel = self._make_card("customSequenceInputPanel", layout_role="sidePanel")
        left_panel.setFixedWidth(230)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        left_layout.addWidget(self._section_label("Wave"))
        self.wave_spin = QSpinBox()
        self.wave_spin.setMinimum(1)
        self.wave_spin.setMaximum(3)
        self.wave_button_group = QButtonGroup(self)
        self.wave_button_group.setExclusive(True)
        wave_row = QHBoxLayout()
        wave_row.setSpacing(0)
        self.wave_buttons: dict[int, QPushButton] = {}
        for value in (1, 2, 3):
            button = self._pill_button(f"W{value}", checked=value == 1)
            button.clicked.connect(
                lambda _checked=False, current=value: self._set_wave_from_button(current)
            )
            self.wave_button_group.addButton(button, value)
            self.wave_buttons[value] = button
            wave_row.addWidget(button)
        left_layout.addLayout(wave_row)

        left_layout.addWidget(self._section_label("Turn"))
        self.turn_spin = QSpinBox()
        self.turn_spin.setMinimum(1)
        self.turn_spin.setMaximum(99)
        left_layout.addWidget(self.turn_spin)

        left_layout.addWidget(self._divider())

        left_layout.addWidget(self._section_label("敌方目标"))
        enemy_row = QHBoxLayout()
        enemy_row.setSpacing(5)
        for index in (1, 2, 3):
            button = QPushButton(f"敌方 {index}")
            button.clicked.connect(
                lambda _checked=False, value=index: self.add_enemy_target_action(value)
            )
            enemy_row.addWidget(button)
        left_layout.addLayout(enemy_row)

        left_layout.addWidget(self._divider())
        left_layout.addWidget(self._section_label("从者技能"))
        servant_grid = QGridLayout()
        servant_grid.setHorizontalSpacing(4)
        servant_grid.setVerticalSpacing(4)
        for servant in (1, 2, 3):
            servant_tag = QLabel(f"从{servant}")
            servant_tag.setProperty("textRole", "muted")
            servant_grid.addWidget(servant_tag, servant - 1, 0)
            for skill in (1, 2, 3):
                button = QPushButton(f"技{skill}")
                button.clicked.connect(
                    lambda _checked=False, actor=servant, value=skill: self._add_servant_skill(actor, value)
                )
                servant_grid.addWidget(button, servant - 1, skill)
            noble_button = QPushButton("NP")
            noble_button.setObjectName("primaryButton")
            noble_button.clicked.connect(
                lambda _checked=False, index=servant: self._add_noble(index)
            )
            servant_grid.addWidget(noble_button, servant - 1, 4)
        left_layout.addLayout(servant_grid)

        left_layout.addWidget(self._divider())
        left_layout.addWidget(self._section_label("御主技能"))
        master_row = QHBoxLayout()
        master_row.setSpacing(5)
        for skill in (1, 2):
            button = QPushButton(f"御主 {skill}")
            button.clicked.connect(
                lambda _checked=False, value=skill: self._add_master_skill(value)
            )
            master_row.addWidget(button)
        left_layout.addLayout(master_row)
        disabled = QPushButton("御主 3 (未支持)")
        disabled.setEnabled(False)
        left_layout.addWidget(disabled)

        left_layout.addStretch(1)
        history_card = self._make_card(layout_role="editorPanel")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(8, 8, 8, 8)
        history_layout.setSpacing(6)
        history_layout.addWidget(self._section_label("最近操作"))
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(120)
        history_layout.addWidget(self.history_list)
        left_layout.addWidget(history_card, stretch=1)
        root.addWidget(left_panel, stretch=0)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(self._build_list_panel("当前回合 · 动作", noble_panel=False), stretch=1)
        top_row.addWidget(self._build_list_panel("当前回合 · 宝具", noble_panel=True), stretch=1)
        center_layout.addLayout(top_row, stretch=1)

        bottom_card = self._make_card(layout_role="toolbar")
        bottom_layout = QHBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(10, 8, 10, 8)
        bottom_layout.setSpacing(6)
        sequence_label = QLabel("序列文件")
        sequence_label.setProperty("textRole", "muted")
        bottom_layout.addWidget(sequence_label)
        self.sequence_name_edit = QLineEdit()
        bottom_layout.addWidget(self.sequence_name_edit, stretch=1)
        load_button = QPushButton("加载")
        bottom_layout.addWidget(load_button)
        center_layout.addWidget(bottom_card, stretch=0)
        root.addWidget(center_panel, stretch=1)

        side_panel = self._make_card("customSequenceSidePanel", layout_role="sidePanel")
        side_panel.setFixedWidth(200)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(10, 10, 10, 10)
        side_layout.setSpacing(10)
        side_layout.addWidget(self._section_label("当前摘要"))
        self.summary_sequence_label = self._value_label("序列：-")
        self.summary_turn_label = self._value_label("回合：-")
        self.summary_actions_label = self._value_label("动作数：0")
        self.summary_nobles_label = self._value_label("宝具数：0")
        for label in (
            self.summary_sequence_label,
            self.summary_turn_label,
            self.summary_actions_label,
            self.summary_nobles_label,
        ):
            side_layout.addWidget(label)

        self.save_button = QPushButton("保存当前配置")
        self.save_button.setObjectName("successButton")
        side_layout.addWidget(self.save_button)

        side_layout.addWidget(self._section_label("Wave 总览"))
        self.wave_overview_list = QListWidget()
        self.wave_overview_list.setMinimumHeight(140)
        side_layout.addWidget(self.wave_overview_list, stretch=1)

        self.status_label = self._value_label("等待编辑")
        side_layout.addWidget(self.status_label)
        root.addWidget(side_panel, stretch=0)

        load_button.clicked.connect(self._load_selected_sequence)
        self.save_button.clicked.connect(self.save_sequence)
        self.wave_spin.valueChanged.connect(self._on_turn_selector_changed)
        self.turn_spin.valueChanged.connect(self._on_turn_selector_changed)

    def _build_list_panel(self, title: str, *, noble_panel: bool) -> QWidget:
        panel = self._make_card(layout_role="editorPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(10, 8, 10, 8)
        header.addWidget(self._section_label(title))
        header.addStretch(1)
        count = QLabel("0 项")
        count.setProperty("textRole", "badge")
        header.addWidget(count)
        layout.addLayout(header)

        body = QVBoxLayout()
        body.setContentsMargins(8, 0, 8, 8)
        body.setSpacing(8)
        list_widget = QListWidget()
        body.addWidget(list_widget, stretch=1)
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        remove_button = QPushButton("删除")
        move_up = QPushButton("↑ 上移")
        move_down = QPushButton("↓ 下移")
        buttons.addWidget(remove_button)
        buttons.addWidget(move_up)
        buttons.addWidget(move_down)
        body.addLayout(buttons)
        layout.addLayout(body, stretch=1)

        if noble_panel:
            self.nobles_list = list_widget
            self.nobles_count_label = count
            remove_button.clicked.connect(self._remove_selected_noble)
            move_up.clicked.connect(lambda: self._move_noble(-1))
            move_down.clicked.connect(lambda: self._move_noble(1))
        else:
            self.actions_list = list_widget
            self.actions_count_label = count
            remove_button.clicked.connect(self._remove_selected_action)
            move_up.clicked.connect(lambda: self._move_action(-1))
            move_down.clicked.connect(lambda: self._move_action(1))
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
        self._refresh_history_and_overview()

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
        self._refresh_history_and_overview()

    def _refresh_lists(self) -> None:
        self.actions_list.clear()
        for action in self._current_turn_state.actions:
            self.actions_list.addItem(format_action_text(action))
        self.nobles_list.clear()
        for noble in self._current_turn_state.nobles:
            self.nobles_list.addItem(format_noble_text(noble))
        self.actions_count_label.setText(f"{len(self._current_turn_state.actions)} 项")
        self.nobles_count_label.setText(f"{len(self._current_turn_state.nobles)} 项")

    def _refresh_side_summary(self) -> None:
        self.summary_sequence_label.setText(f"序列：{self.current_sequence_name() or '-'}")
        self.summary_turn_label.setText(
            f"当前：Wave {self.wave_spin.value()} / Turn {self.turn_spin.value()}"
        )
        self.summary_actions_label.setText(
            f"动作数：{len(self._current_turn_state.actions)}"
        )
        self.summary_nobles_label.setText(
            f"宝具数：{len(self._current_turn_state.nobles)}"
        )

    def _refresh_history_and_overview(self) -> None:
        self.history_list.clear()
        if not self.turn_map:
            self.history_list.addItem("待配置…")
        else:
            for (wave, turn), state in sorted(self.turn_map.items())[-6:]:
                action_count = len(state.actions)
                noble_count = len(state.nobles)
                self.history_list.addItem(
                    f"W{wave}T{turn} · 技能×{action_count} · 宝具×{noble_count}"
                )

        self.wave_overview_list.clear()
        if not self.turn_map:
            self.wave_overview_list.addItem("未配置")
            return
        for (wave, turn), state in sorted(self.turn_map.items()):
            action_count = len(state.actions)
            noble_count = len(state.nobles)
            self.wave_overview_list.addItem(
                f"W{wave} T{turn} · 技能×{action_count} · 宝具×{noble_count}"
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

    def _on_turn_selector_changed(self, *_args) -> None:
        self._sync_wave_buttons()
        self._load_current_turn_state()

    def _set_wave_from_button(self, wave: int) -> None:
        self.wave_spin.setValue(wave)

    def _sync_wave_buttons(self) -> None:
        current = self.wave_spin.value()
        for value, button in self.wave_buttons.items():
            button.setChecked(value == current)

    def _pill_button(self, text: str, *, checked: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("buttonRole", "pillToggle")
        button.setCheckable(True)
        button.setChecked(checked)
        return button

    def _make_card(
        self,
        object_name: str | None = None,
        *,
        layout_role: str | None = None,
    ) -> QFrame:
        frame = QFrame()
        if object_name:
            frame.setObjectName(object_name)
        frame.setProperty("panelRole", "card")
        if layout_role:
            frame.setProperty("layoutRole", layout_role)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        return frame

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("textRole", "section")
        return label

    def _value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setProperty("textRole", "muted")
        return label

    def _divider(self) -> QFrame:
        divider = QFrame()
        divider.setProperty("separatorRole", "divider")
        divider.setFixedHeight(1)
        return divider
