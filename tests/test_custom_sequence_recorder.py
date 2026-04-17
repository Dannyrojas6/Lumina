from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from core.shared.config_models import CustomSequenceAction
from scripts import custom_sequence_recorder as recorder


class CustomSequenceRecorderLogicTest(unittest.TestCase):
    def test_build_ui_metrics_scales_up_for_high_resolution(self) -> None:
        metrics = recorder.build_ui_metrics(2560, 1440)

        self.assertEqual(metrics.scale, 1.2)
        self.assertGreater(metrics.window_width, 1600)
        self.assertGreater(metrics.sidebar_width, 460)
        self.assertGreater(metrics.title_font_size, 12)
        self.assertEqual(metrics.sidebar_list_columns, 2)
        self.assertGreaterEqual(metrics.status_lines, 4)

    def test_step_wave_turn_together_keeps_wave_and_turn_in_sync(self) -> None:
        self.assertEqual(recorder.step_wave_turn_together(1, 3, 1), (2, 4))
        self.assertEqual(recorder.step_wave_turn_together(2, 4, -1), (1, 3))
        self.assertEqual(recorder.step_wave_turn_together(1, 1, -1), (1, 1))

    def test_load_turn_map_reads_selected_sequence_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            sequence_dir = config_dir / "custom_sequences"
            sequence_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            sequence_path = sequence_dir / "daily.yaml"
            config_path.write_text(
                dedent(
                    """
                    battle_mode: main
                    custom_sequence_battle:
                      sequence: daily.yaml
                    skill_sequence: []
                    """
                ),
                encoding="utf-8",
            )
            sequence_path.write_text(
                dedent(
                    """
                    turns:
                      - wave: 1
                        turn: 1
                        actions:
                          - type: enemy_target
                            target: 2
                          - type: servant_skill
                            actor: 1
                            skill: 3
                            target: null
                        nobles: [3]
                    """
                ),
                encoding="utf-8",
            )

            turn_map = recorder.load_turn_map(config_path)

            self.assertEqual(
                recorder.load_selected_sequence_name(config_path),
                "daily.yaml",
            )
            self.assertEqual(sorted(turn_map), [(1, 1)])
            turn_state = turn_map[(1, 1)]
            self.assertEqual(turn_state.nobles, [3])
            self.assertEqual(
                turn_state.actions,
                [
                    CustomSequenceAction(type="enemy_target", target=2),
                    CustomSequenceAction(
                        type="servant_skill",
                        actor=1,
                        skill=3,
                        target=None,
                    ),
                ],
            )

    def test_collect_serializable_turns_skips_empty_turns(self) -> None:
        turn_map = {
            (1, 1): recorder.TurnEditorState(),
            (1, 2): recorder.TurnEditorState(
                actions=[CustomSequenceAction(type="enemy_target", target=1)],
                nobles=[],
            ),
        }

        turns = recorder.collect_serializable_turns(turn_map)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].wave, 1)
        self.assertEqual(turns[0].turn, 2)

    def test_render_sequence_yaml_serializes_actions_and_nobles(self) -> None:
        turn_map = {
            (1, 1): recorder.TurnEditorState(
                actions=[
                    CustomSequenceAction(type="enemy_target", target=2),
                    CustomSequenceAction(
                        type="servant_skill",
                        actor=1,
                        skill=1,
                        target=None,
                    ),
                    CustomSequenceAction(
                        type="master_skill",
                        skill=2,
                        target=3,
                    ),
                ],
                nobles=[3, 1],
            )
        }

        block = recorder.render_sequence_yaml(turn_map)

        self.assertIn("turns:", block)
        self.assertIn("- wave: 1", block)
        self.assertIn("turn: 1", block)
        self.assertIn("type: enemy_target", block)
        self.assertIn("type: servant_skill", block)
        self.assertIn("type: master_skill", block)
        self.assertIn("nobles: [3, 1]", block)
        self.assertNotIn("custom_sequence_battle:", block)

    def test_replace_custom_sequence_selector_block_preserves_other_content(self) -> None:
        original = dedent(
            """
            loop_count: 10
            battle_mode: main
            custom_sequence_battle:
              sequence: old.yaml
            # keep me
            skill_sequence:
              - 1
            """
        ).strip()
        replacement = dedent(
            """
            custom_sequence_battle:
              sequence: new.yaml
            """
        ).strip()

        updated = recorder.replace_custom_sequence_selector_block(original, replacement)

        self.assertIn("loop_count: 10", updated)
        self.assertIn("battle_mode: main", updated)
        self.assertIn("# keep me", updated)
        self.assertIn("skill_sequence:", updated)
        self.assertEqual(updated.count("custom_sequence_battle:"), 1)
        self.assertIn("sequence: new.yaml", updated)

    def test_save_turn_map_updates_selector_and_keeps_battle_mode(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    battle_mode: main
                    custom_sequence_battle:
                      sequence: ""
                    skill_sequence:
                      - 1
                    """
                ),
                encoding="utf-8",
            )

            recorder.save_turn_map(
                config_path,
                "daily.yaml",
                {
                    (1, 1): recorder.TurnEditorState(
                        actions=[CustomSequenceAction(type="enemy_target", target=3)],
                        nobles=[2],
                    )
                },
            )

            config_text = config_path.read_text(encoding="utf-8")
            sequence_text = (
                config_dir / "custom_sequences" / "daily.yaml"
            ).read_text(encoding="utf-8")

            self.assertIn("battle_mode: main", config_text)
            self.assertIn("sequence: daily.yaml", config_text)
            self.assertNotIn("battle_mode: custom_sequence", config_text)
            self.assertIn("turns:", sequence_text)
            self.assertIn("nobles: [2]", sequence_text)

    def test_save_then_reload_round_trips_with_external_sequence_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    loop_count: 10
                    battle_mode: main
                    custom_sequence_battle:
                      sequence: boss.yaml
                    skill_sequence:
                      - 1
                    """
                ),
                encoding="utf-8",
            )
            expected = {
                (1, 1): recorder.TurnEditorState(
                    actions=[
                        CustomSequenceAction(type="enemy_target", target=2),
                        CustomSequenceAction(
                            type="servant_skill",
                            actor=2,
                            skill=3,
                            target=1,
                        ),
                    ],
                    nobles=[3],
                ),
                (2, 1): recorder.TurnEditorState(
                    actions=[],
                    nobles=[1, 2],
                ),
            }

            recorder.save_turn_map(config_path, "boss.yaml", expected)
            actual = recorder.load_turn_map(config_path)

            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
