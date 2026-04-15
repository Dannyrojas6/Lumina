import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from adbutils.errors import AdbError

from core.device.adb_controller import AdbController
from core.device.profile import DeviceProfile


def _profile() -> DeviceProfile:
    return DeviceProfile(
        name="mumu_1920x1080",
        width=1920,
        height=1080,
        device_discovery_timeout=0.1,
        device_discovery_interval=0.0,
        operation_retry_count=2,
        operation_retry_delay=0.0,
        attack_button_delay=0.5,
        card_select_delay=0.3,
        target_select_delay=0.3,
    )


def _entry(serial: str, state: str = "device") -> SimpleNamespace:
    return SimpleNamespace(serial=serial, state=state)


class AdbControllerStartupRecoveryTest(unittest.TestCase):
    @patch("core.device.adb_controller.find_adb_path", return_value="adb")
    @patch("core.device.adb_controller.time.sleep", return_value=None)
    @patch.object(AdbController, "_validate_resolution")
    def test_init_recovers_and_binds_unique_device_when_serial_blank(
        self,
        _validate_resolution_mock: Mock,
        _sleep_mock: Mock,
        _find_adb_path_mock: Mock,
    ) -> None:
        fake_device = SimpleNamespace(serial="127.0.0.1:7555")
        with patch(
            "core.device.adb_controller.adb.device_list",
            side_effect=[
                [],
                [_entry("127.0.0.1:7555", "device")],
            ],
        ), patch(
            "core.device.adb_controller.adb.device",
            return_value=fake_device,
        ) as device_mock, patch(
            "core.device.adb_controller.subprocess.run",
        ) as run_mock:
            controller = AdbController(
                serial=None,
                connect_targets=["127.0.0.1:7555"],
                profile=_profile(),
            )

        self.assertEqual(controller.serial, "127.0.0.1:7555")
        self.assertEqual(
            [call.args[0][1] for call in run_mock.call_args_list],
            ["start-server", "kill-server", "start-server", "connect"],
        )
        self.assertEqual(
            run_mock.call_args_list[-1].args[0],
            ["adb", "connect", "127.0.0.1:7555"],
        )
        device_mock.assert_called_once_with(serial="127.0.0.1:7555")

    @patch("core.device.adb_controller.find_adb_path", return_value="adb")
    @patch("core.device.adb_controller.time.sleep", return_value=None)
    @patch.object(AdbController, "_validate_resolution")
    def test_init_recovers_and_binds_configured_serial(
        self,
        _validate_resolution_mock: Mock,
        _sleep_mock: Mock,
        _find_adb_path_mock: Mock,
    ) -> None:
        fake_device = SimpleNamespace(serial="emulator-5560")
        with patch(
            "core.device.adb_controller.adb.device_list",
            side_effect=[
                [_entry("emulator-5554", "device")],
                [_entry("emulator-5554", "device"), _entry("emulator-5560", "device")],
            ],
        ), patch(
            "core.device.adb_controller.adb.device",
            return_value=fake_device,
        ) as device_mock, patch(
            "core.device.adb_controller.subprocess.run",
        ):
            controller = AdbController(
                serial="emulator-5560",
                connect_targets=["127.0.0.1:7555"],
                profile=_profile(),
            )

        self.assertEqual(controller.serial, "emulator-5560")
        device_mock.assert_called_once_with(serial="emulator-5560")

    @patch("core.device.adb_controller.find_adb_path", return_value="adb")
    @patch("core.device.adb_controller.time.sleep", return_value=None)
    @patch.object(AdbController, "_validate_resolution")
    def test_init_fails_when_multiple_ready_devices_and_serial_blank(
        self,
        _validate_resolution_mock: Mock,
        _sleep_mock: Mock,
        _find_adb_path_mock: Mock,
    ) -> None:
        with patch(
            "core.device.adb_controller.adb.device_list",
            side_effect=[
                [],
                [_entry("emulator-5554", "device"), _entry("emulator-5560", "device")],
            ],
        ), patch(
            "core.device.adb_controller.subprocess.run",
        ):
            with self.assertRaisesRegex(RuntimeError, "multiple ready adb devices"):
                AdbController(
                    serial=None,
                    connect_targets=["127.0.0.1:7555"],
                    profile=_profile(),
                )

    @patch("core.device.adb_controller.find_adb_path", return_value="adb")
    @patch("core.device.adb_controller.time.sleep", return_value=None)
    @patch.object(AdbController, "_validate_resolution")
    def test_init_ignores_offline_and_unauthorized_devices(
        self,
        _validate_resolution_mock: Mock,
        _sleep_mock: Mock,
        _find_adb_path_mock: Mock,
    ) -> None:
        fake_device = SimpleNamespace(serial="127.0.0.1:7555")
        with patch(
            "core.device.adb_controller.adb.device_list",
            side_effect=[
                [_entry("emulator-5554", "offline"), _entry("emulator-5560", "unauthorized")],
                [
                    _entry("emulator-5554", "offline"),
                    _entry("emulator-5560", "unauthorized"),
                    _entry("127.0.0.1:7555", "device"),
                ],
            ],
        ), patch(
            "core.device.adb_controller.adb.device",
            return_value=fake_device,
        ), patch(
            "core.device.adb_controller.subprocess.run",
        ):
            controller = AdbController(
                serial=None,
                connect_targets=["127.0.0.1:7555"],
                profile=_profile(),
            )

        self.assertEqual(controller.serial, "127.0.0.1:7555")


class AdbControllerRuntimeFailureTest(unittest.TestCase):
    def _make_runtime_controller(self, device: SimpleNamespace) -> AdbController:
        controller = object.__new__(AdbController)
        controller.profile = _profile()
        controller.device_discovery_timeout = 0.1
        controller.device_discovery_interval = 0.0
        controller.operation_retry_count = 2
        controller.operation_retry_delay = 0.0
        controller.device = device
        controller._device_serial = device.serial
        return controller

    def test_runtime_screenshot_failure_stops_without_recovery(self) -> None:
        device = SimpleNamespace(
            serial="emulator-5560",
            screenshot=Mock(side_effect=AdbError("device disconnected")),
        )
        controller = self._make_runtime_controller(device)

        with TemporaryDirectory() as tmp_dir, patch(
            "core.device.adb_controller.subprocess.run"
        ) as run_mock, self.assertRaisesRegex(
            RuntimeError,
            "运行中 ADB 操作失败: screenshot; serial=emulator-5560; 已停止主链，未执行运行中重连",
        ):
            controller.screenshot(str(Path(tmp_dir) / "screen.png"))

        run_mock.assert_not_called()

    def test_runtime_click_failure_stops_without_recovery(self) -> None:
        device = SimpleNamespace(
            serial="emulator-5560",
            click=Mock(side_effect=AdbError("device disconnected")),
        )
        controller = self._make_runtime_controller(device)

        with patch("core.device.adb_controller.subprocess.run") as run_mock, self.assertRaisesRegex(
            RuntimeError,
            "运行中 ADB 操作失败: click; serial=emulator-5560; 已停止主链，未执行运行中重连",
        ):
            controller.click(10, 20)

        run_mock.assert_not_called()

    def test_runtime_swipe_failure_stops_without_recovery(self) -> None:
        device = SimpleNamespace(
            serial="emulator-5560",
            swipe=Mock(side_effect=AdbError("device disconnected")),
        )
        controller = self._make_runtime_controller(device)

        with patch("core.device.adb_controller.subprocess.run") as run_mock, self.assertRaisesRegex(
            RuntimeError,
            "运行中 ADB 操作失败: swipe; serial=emulator-5560; 已停止主链，未执行运行中重连",
        ):
            controller.swipe(10, 20, 30, 40)

        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
