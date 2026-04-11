import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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


if __name__ == "__main__":
    unittest.main()
