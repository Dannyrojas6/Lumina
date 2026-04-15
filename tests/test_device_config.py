import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.shared.config_models import BattleConfig


class DeviceConfigTest(unittest.TestCase):
    def test_loads_device_profile_serial_and_connect_targets_from_yaml(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "battle_config.yaml"
            config_path.write_text(
                """
device:
  profile: mumu_1920x1080
  serial: ""
  connect_targets:
    - 127.0.0.1:7555
""",
                encoding="utf-8",
            )

            config = BattleConfig.from_yaml(str(config_path))

        self.assertEqual(config.device.profile, "mumu_1920x1080")
        self.assertEqual(config.device.serial, "")
        self.assertEqual(config.device.connect_targets, ["127.0.0.1:7555"])


if __name__ == "__main__":
    unittest.main()
