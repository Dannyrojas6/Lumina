import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from core.device import MUMU_1920X1080
from core.runtime.startup_check import (
    validate_runtime_prerequisites,
    validate_support_servant_resources,
)
from core.shared import BattleConfig, DeviceConfig, ResourceCatalog, SmartBattleFrontlineSlot


class StartupCheckTest(unittest.TestCase):
    def test_validate_runtime_prerequisites_rejects_mismatched_resolution(self) -> None:
        resources = SimpleNamespace(
            state_templates={},
            template=lambda *args, **kwargs: __file__,
            support_class_template=lambda *args, **kwargs: __file__,
        )

        with self.assertRaisesRegex(RuntimeError, "device resolution does not match configured profile"):
            validate_runtime_prerequisites(
                BattleConfig(device=DeviceConfig(profile="mumu_1920x1080")),
                resources,  # type: ignore[arg-type]
                MUMU_1920X1080,
                device_resolution=(1280, 720),
            )

    def test_validate_support_servant_resources_requires_bank_and_meta(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            servant_dir = root / "local_data" / "servants" / "berserker" / "morgan"
            atlas_dir = servant_dir / "atlas" / "faces"
            atlas_dir.mkdir(parents=True)
            (atlas_dir / "sample.png").write_bytes(b"png")
            (servant_dir / "manifest.yaml").write_text(
                """
servant_name: berserker/morgan
display_name: Morgan
class_name: berserker
support_recognition:
  source_dir: atlas/faces
  generated_dir: support/generated
  reference_bank: support/generated/reference_bank.npz
  reference_meta: support/generated/reference_meta.json
skills: []
""",
                encoding="utf-8",
            )
            catalog = ResourceCatalog(
                assets_dir=str(root / "assets"),
                servants_dir=str(root / "local_data" / "servants"),
            )

            with self.assertRaisesRegex(FileNotFoundError, "reference_bank"):
                validate_support_servant_resources(catalog, "berserker/morgan")

    def test_validate_runtime_prerequisites_accepts_existing_templates_and_support_assets(
        self,
    ) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            assets = root / "assets"
            ui = assets / "ui" / "common"
            states = assets / "states"
            for state_name, filename in (
                ("support_select", "support_select.png"),
                ("team_confirm", "team_confirm.png"),
                ("loading_tips", "tips.png"),
                ("dialog", "skip.png"),
                ("card_select", "fight_speed.png"),
                ("battle_ready", "fight_menu.png"),
                ("main_menu", "main_menu.png"),
            ):
                path = states / state_name
                path.mkdir(parents=True, exist_ok=True)
                (path / filename).write_bytes(b"x")
            ui.mkdir(parents=True, exist_ok=True)
            support_ui = assets / "ui" / "support_select"
            support_ui.mkdir(parents=True, exist_ok=True)
            for filename in (
                "fight_result_1.png",
                "fight_result_2.png",
                "fight_result_3.png",
                "next.png",
                "continue_battle.png",
                "close.png",
            ):
                (ui / filename).write_bytes(b"x")
            ap_ui = assets / "ui" / "ap"
            ap_ui.mkdir(parents=True, exist_ok=True)
            for filename in (
                "ap_recovery.png",
                "bronzed_cobalt_fruit.png",
                "confirm.png",
            ):
                (ap_ui / filename).write_bytes(b"x")
            for filename in ("all_class.png", "berserker.png"):
                (support_ui / filename).write_bytes(b"x")

            servant_dir = root / "local_data" / "servants" / "berserker" / "morgan"
            atlas_dir = servant_dir / "atlas" / "faces" / "ascension"
            generated_dir = servant_dir / "support" / "generated"
            atlas_dir.mkdir(parents=True)
            generated_dir.mkdir(parents=True)
            (atlas_dir / "sample.png").write_bytes(b"png")
            (generated_dir / "reference_bank.npz").write_bytes(b"bank")
            (generated_dir / "reference_meta.json").write_text("{}", encoding="utf-8")
            (servant_dir / "manifest.yaml").write_text(
                """
servant_name: berserker/morgan
display_name: Morgan
class_name: berserker
support_recognition:
  source_dir: atlas/faces
  generated_dir: support/generated
  reference_bank: support/generated/reference_bank.npz
  reference_meta: support/generated/reference_meta.json
skills: []
""",
                encoding="utf-8",
            )

            catalog = ResourceCatalog(
                assets_dir=str(assets),
                servants_dir=str(root / "local_data" / "servants"),
            )
            config = BattleConfig(
                device=DeviceConfig(profile="mumu_1920x1080", serial="emulator-5560")
            )
            config.support.servant = "berserker/morgan"

            validate_runtime_prerequisites(
                config,
                catalog,
                MUMU_1920X1080,
                device_resolution=(1920, 1080),
            )

    def test_validate_runtime_prerequisites_requires_ap_recovery_templates(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            assets = root / "assets"
            ui = assets / "ui" / "common"
            states = assets / "states"
            for state_name, filename in (
                ("support_select", "support_select.png"),
                ("team_confirm", "team_confirm.png"),
                ("loading_tips", "tips.png"),
                ("dialog", "skip.png"),
                ("card_select", "fight_speed.png"),
                ("battle_ready", "fight_menu.png"),
                ("main_menu", "main_menu.png"),
            ):
                path = states / state_name
                path.mkdir(parents=True, exist_ok=True)
                (path / filename).write_bytes(b"x")
            ui.mkdir(parents=True, exist_ok=True)
            support_ui = assets / "ui" / "support_select"
            support_ui.mkdir(parents=True, exist_ok=True)
            for filename in (
                "fight_result_1.png",
                "fight_result_2.png",
                "fight_result_3.png",
                "next.png",
                "continue_battle.png",
                "close.png",
            ):
                (ui / filename).write_bytes(b"x")
            for filename in ("all_class.png", "berserker.png"):
                (support_ui / filename).write_bytes(b"x")

            catalog = ResourceCatalog(
                assets_dir=str(assets),
                servants_dir=str(root / "local_data" / "servants"),
            )
            config = BattleConfig(
                device=DeviceConfig(profile="mumu_1920x1080", serial="emulator-5560")
            )

            with self.assertRaisesRegex(FileNotFoundError, "ap_recovery"):
                validate_runtime_prerequisites(
                    config,
                    catalog,
                    MUMU_1920X1080,
                    device_resolution=(1920, 1080),
                )

    def test_custom_sequence_mode_does_not_require_smart_battle_frontline_assets(self) -> None:
        resources = SimpleNamespace(
            state_templates={},
            template=lambda *args, **kwargs: __file__,
            support_class_template=lambda *args, **kwargs: __file__,
            load_servant_manifest=Mock(side_effect=AssertionError("should not load frontline manifests")),
        )
        config = BattleConfig(
            battle_mode="custom_sequence",
            device=DeviceConfig(profile="mumu_1920x1080"),
        )
        config.smart_battle.enabled = True
        config.smart_battle.frontline = [
            SmartBattleFrontlineSlot(slot=1, servant="berserker/morgan", role="attacker", is_support=True)
        ]

        validate_runtime_prerequisites(
            config,
            resources,  # type: ignore[arg-type]
            MUMU_1920X1080,
            device_resolution=(1920, 1080),
        )


if __name__ == "__main__":
    unittest.main()
