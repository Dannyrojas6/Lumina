import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from core.shared.config_models import BattleConfig
from core.shared.resource_catalog import ResourceCatalog


class BattleConfigTest(unittest.TestCase):
    def test_loads_command_card_priority_from_yaml(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                """
smart_battle:
  enabled: true
  frontline:
    - slot: 1
      servant: caster/zhuge_liang
      role: support
      is_support: false
    - slot: 2
      servant: caster/altria_caster
      role: support
      is_support: false
    - slot: 3
      servant: berserker/morgan
      role: attacker
      is_support: true
  command_card_priority:
    - berserker/morgan
    - caster/zhuge_liang
    - caster/altria_caster
""",
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))

            self.assertEqual(
                config.smart_battle.command_card_priority,
                [
                    "berserker/morgan",
                    "caster/zhuge_liang",
                    "caster/altria_caster",
                ],
            )

    def test_rejects_deprecated_fail_mode_field(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    smart_battle:
                      enabled: true
                      fail_mode: conservative
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "fail_mode.*已废弃|deprecated"):
                BattleConfig.from_yaml(str(config_path))

    def test_rejects_deprecated_wave_plan_field(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    smart_battle:
                      enabled: true
                      wave_plan:
                        - wave: 1
                          actions: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "wave_plan.*已废弃|deprecated"):
                BattleConfig.from_yaml(str(config_path))

    def test_resource_catalog_resolves_defaults_from_repo_root(self) -> None:
        previous_cwd = Path.cwd()
        with TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                catalog = ResourceCatalog()
            finally:
                os.chdir(previous_cwd)

        repo_root = Path(__file__).resolve().parents[1]
        self.assertEqual(Path(catalog.assets_dir), repo_root / "assets")
        self.assertEqual(
            Path(catalog.servants_dir), repo_root / "local_data" / "servants"
        )
        self.assertEqual(
            Path(catalog.screen_path),
            repo_root / "assets" / "screenshots" / "screen.png",
        )
        self.assertEqual(
            Path(catalog.ocr_debug_dir),
            repo_root / "assets" / "screenshots" / "ocr",
        )
        self.assertEqual(
            Path(catalog.support_debug_dir),
            repo_root / "assets" / "screenshots" / "support_recognition",
        )

    def test_continue_battle_defaults_to_true(self) -> None:
        config = BattleConfig.default()

        self.assertTrue(config.continue_battle)

    def test_loads_continue_battle_from_yaml(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    continue_battle: false
                    """
                ),
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))

            self.assertFalse(config.continue_battle)

    def test_default_skill_target_defaults_to_three(self) -> None:
        config = BattleConfig.default()

        self.assertEqual(config.default_skill_target, 3)

    def test_battle_mode_defaults_to_main(self) -> None:
        config = BattleConfig.default()

        self.assertEqual(config.battle_mode, "main")

    def test_loads_default_skill_target_from_yaml(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    default_skill_target: 2
                    """
                ),
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))

            self.assertEqual(config.default_skill_target, 2)

    def test_loads_custom_sequence_battle_from_yaml(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            sequence_dir = config_dir / "custom_sequences"
            sequence_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            (sequence_dir / "daily.yaml").write_text(
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
                            skill: 1
                            target: null
                          - type: master_skill
                            skill: 2
                            target: 3
                        nobles: [3]
                    """
                ),
                encoding="utf-8",
            )
            config_path.write_text(
                dedent(
                    """
                    battle_mode: custom_sequence
                    custom_sequence_battle:
                      sequence: daily.yaml
                    """
                ),
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))
            plan = config.custom_sequence_battle.find_turn_plan(1, 1)

            self.assertEqual(config.battle_mode, "custom_sequence")
            self.assertIsNotNone(plan)
            assert plan is not None
            self.assertEqual(plan.nobles, [3])
            self.assertEqual([action.type for action in plan.actions], [
                "enemy_target",
                "servant_skill",
                "master_skill",
            ])

    def test_rejects_custom_sequence_master_skill_three(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            sequence_dir = config_dir / "custom_sequences"
            sequence_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            (sequence_dir / "invalid.yaml").write_text(
                dedent(
                    """
                    turns:
                      - wave: 1
                        turn: 1
                        actions:
                          - type: master_skill
                            skill: 3
                            target: null
                    """
                ),
                encoding="utf-8",
            )
            config_path.write_text(
                dedent(
                    """
                    battle_mode: custom_sequence
                    custom_sequence_battle:
                      sequence: invalid.yaml
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "master_skill.*3|换人"):
                BattleConfig.from_yaml(str(config_path))

    def test_rejects_duplicate_custom_sequence_turns(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            sequence_dir = config_dir / "custom_sequences"
            sequence_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            (sequence_dir / "duplicate.yaml").write_text(
                dedent(
                    """
                    turns:
                      - wave: 1
                        turn: 1
                        actions: []
                      - wave: 1
                        turn: 1
                        actions: []
                    """
                ),
                encoding="utf-8",
            )
            config_path.write_text(
                dedent(
                    """
                    battle_mode: custom_sequence
                    custom_sequence_battle:
                      sequence: duplicate.yaml
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "duplicate|重复"):
                BattleConfig.from_yaml(str(config_path))

    def test_rejects_missing_custom_sequence_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    battle_mode: custom_sequence
                    custom_sequence_battle:
                      sequence: missing.yaml
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(FileNotFoundError, "missing.yaml"):
                BattleConfig.from_yaml(str(config_path))

    def test_main_mode_allows_missing_custom_sequence_file_without_loading(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "config"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "battle_config.yaml"
            config_path.write_text(
                dedent(
                    """
                    battle_mode: main
                    custom_sequence_battle:
                      sequence: missing.yaml
                    """
                ),
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))

            self.assertEqual(config.battle_mode, "main")
            self.assertEqual(config.custom_sequence_battle.sequence, "missing.yaml")
            self.assertEqual(config.custom_sequence_battle.turns, [])


if __name__ == "__main__":
    unittest.main()
