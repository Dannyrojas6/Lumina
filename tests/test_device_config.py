import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.shared.config_models import BattleConfig


class DeviceConfigTest(unittest.TestCase):
    def test_loads_device_serial_and_connect_targets_from_yaml(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                """
device:
  serial: ""
  connect_targets:
    - 127.0.0.1:7555
""",
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))

        self.assertEqual(config.device.serial, "")
        self.assertEqual(config.device.connect_targets, ["127.0.0.1:7555"])

    def test_rejects_device_profile_field(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                """
device:
  profile: mumu_1920x1080
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "device.profile.*已废弃|device.profile.*unsupported"):
                BattleConfig.from_yaml(str(config_path))


if __name__ == "__main__":
    unittest.main()
