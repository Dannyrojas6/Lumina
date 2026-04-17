"""ADB 设备适配层，负责连接设备和执行基础触控。"""

from __future__ import annotations

import io
import logging
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from adbutils import AdbDevice, adb
from adbutils.errors import AdbError
from PIL import Image

from core.device.profile import DeviceProfile, MUMU_1920X1080

log = logging.getLogger("core.adb_controller")

DEFAULT_SCREENSHOT_TIMEOUT = 10.0


def find_adb_path() -> str:
    """优先从 PATH 查找 adb，不存在时再使用平台回退路径。"""
    in_path = shutil.which("adb")
    if in_path:
        log.debug("use system adb: %s", in_path)
        return in_path

    fallbacks = {
        "Windows": [
            r"C:\Users\kk\scoop\apps\adb\current\platform-tools\adb.exe",
            r"C:\platform-tools\adb.exe",
        ],
        "Linux": ["/usr/bin/adb"],
    }
    system = platform.system()
    for path in fallbacks.get(system, []):
        if Path(path).exists():
            log.debug("use fallback adb: %s", path)
            return path
    raise FileNotFoundError(
        "can't find adb! please check adb path or install adb tools."
    )


def start_adb_server(adb_path: Optional[str] = None) -> None:
    """启动 adb server；如果已经启动，命令会安全返回。"""
    path = adb_path or find_adb_path()
    subprocess.run([path, "start-server"], check=False, capture_output=True, text=True)
    log.info("ADB Server is activated")


class AdbController:
    """对 `adbutils` 做一层封装，统一固定 profile 下的点击、滑动和截图。"""

    def __init__(
        self,
        serial: Optional[str] = None,
        *,
        connect_targets: Optional[list[str]] = None,
        profile: DeviceProfile = MUMU_1920X1080,
    ) -> None:
        self.profile = profile
        self.device_discovery_timeout = profile.device_discovery_timeout
        self.device_discovery_interval = profile.device_discovery_interval
        self.operation_retry_count = profile.operation_retry_count
        self.operation_retry_delay = profile.operation_retry_delay
        self.screenshot_timeout = DEFAULT_SCREENSHOT_TIMEOUT
        self.adb_path = find_adb_path()
        self.connect_targets = [target for target in (connect_targets or []) if target]
        self._attempted_connect_targets: list[str] = []
        self._runtime_ready = False

        log.info("use adb path: %s", self.adb_path)
        self.device = self._startup_connect(serial)
        self._device_serial = self.device.serial
        self._validate_resolution()
        self._runtime_ready = True

    def _run_adb_command(self, *args: str) -> subprocess.CompletedProcess[str]:
        """执行一条 adb 命令。"""
        command = [self.adb_path, *args]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        log.debug("run adb command: %s", " ".join(command))
        return result

    def _list_device_entries(self) -> dict[str, list[str]]:
        """按状态整理当前 adb 设备。"""
        entries = {"device": [], "offline": [], "unauthorized": [], "other": []}
        for item in adb.device_list():
            serial = str(getattr(item, "serial", "")).strip()
            if not serial:
                continue
            state = str(getattr(item, "state", "device") or "device").strip().lower()
            if state in entries:
                entries[state].append(serial)
            else:
                entries["other"].append(f"{serial}({state})")
        return entries

    def _format_device_entries(self, entries: dict[str, list[str]]) -> str:
        """将设备状态整理成可读文本。"""
        parts: list[str] = []
        for key in ("device", "offline", "unauthorized", "other"):
            values = entries.get(key, [])
            if values:
                parts.append(f"{key}={values}")
        if self._attempted_connect_targets:
            parts.append(f"attempted_connect_targets={self._attempted_connect_targets}")
        return ", ".join(parts) if parts else "no devices"

    def _attempt_connect_targets(self) -> None:
        """按配置尝试 adb connect。"""
        self._attempted_connect_targets = []
        for target in self.connect_targets:
            self._attempted_connect_targets.append(target)
            self._run_adb_command("connect", target)

    def _full_startup_recover(self) -> dict[str, list[str]]:
        """启动阶段执行一次完整 adb 恢复。"""
        self._run_adb_command("kill-server")
        self._run_adb_command("start-server")
        self._attempt_connect_targets()
        return self._list_device_entries()

    def _select_ready_serial(
        self,
        serial: Optional[str],
        entries: dict[str, list[str]],
    ) -> str:
        """从当前设备状态里选出可用设备。"""
        ready = entries.get("device", [])
        offline = entries.get("offline", [])
        unauthorized = entries.get("unauthorized", [])
        if serial:
            if serial in ready:
                return serial
            if serial in offline:
                raise RuntimeError(
                    f"configured adb serial is offline: {serial}; {self._format_device_entries(entries)}"
                )
            if serial in unauthorized:
                raise RuntimeError(
                    f"configured adb serial is unauthorized: {serial}; {self._format_device_entries(entries)}"
                )
            raise RuntimeError(
                f"configured adb serial not found: {serial}; {self._format_device_entries(entries)}"
            )

        if len(ready) == 1:
            return ready[0]
        if len(ready) > 1:
            raise RuntimeError(
                "multiple ready adb devices found: "
                f"{ready}. please set device.serial explicitly."
            )
        raise RuntimeError(f"no ready adb device found; {self._format_device_entries(entries)}")

    def _startup_connect(self, serial: Optional[str]) -> AdbDevice:
        """启动阶段绑定可用设备，必要时执行一次完整恢复。"""
        self._run_adb_command("start-server")
        before = self._list_device_entries()
        log.info("startup adb states before recover: %s", self._format_device_entries(before))
        try:
            selected_serial = self._select_ready_serial(serial, before)
            log.info("startup adb bind without recover: %s", selected_serial)
            return adb.device(serial=selected_serial)
        except RuntimeError as initial_error:
            log.warning("startup adb needs recovery: %s", initial_error)

        after = self._full_startup_recover()
        log.info("startup adb states after recover: %s", self._format_device_entries(after))
        selected_serial = self._select_ready_serial(serial, after)
        log.info("startup adb bound serial: %s", selected_serial)
        return adb.device(serial=selected_serial)

    def _validate_resolution(self) -> None:
        """校验当前设备分辨率与固定 profile 一致。"""
        w, h = self._read_resolution()
        if w < h:
            w, h = h, w
        log.info("current resolution: %sx%s", w, h)
        if (w, h) != (self.profile.width, self.profile.height):
            raise RuntimeError(
                "device resolution does not match configured profile "
                f"{self.profile.name}: expected {self.profile.width}x{self.profile.height}, got {w}x{h}"
            )
        log.info("device profile matched: %s", self.profile.name)

    def _read_resolution(self) -> tuple[int, int]:
        """尽量从稳定来源读取设备分辨率。"""
        wm_size = self._run_with_retry("read_resolution", lambda: self.device.shell("wm size"))
        matched = re.search(r"(\d+)x(\d+)", wm_size)
        if matched:
            return int(matched.group(1)), int(matched.group(2))

        info = self._run_with_retry("read_resolution_info", lambda: self.device.info)
        display = info.get("display")
        if isinstance(display, dict):
            width = display.get("width")
            height = display.get("height")
            if width and height:
                return int(width), int(height)

        width = info.get("width")
        height = info.get("height")
        if width and height:
            return int(width), int(height)

        raise RuntimeError(f"failed to read device resolution from adb: {info}")

    def _is_retryable_error(self, exc: Exception) -> bool:
        """判断当前异常是否适合尝试同设备短重试。"""
        if isinstance(exc, (AdbError, BrokenPipeError, ConnectionResetError, TimeoutError, OSError)):
            return True
        return "closed" in str(exc).lower()

    def _wrap_operation_error(self, action_name: str, exc: Exception) -> RuntimeError:
        """将启动期和运行期的 adb 异常包装成清晰错误。"""
        serial = getattr(self, "_device_serial", getattr(self.device, "serial", "unknown"))
        if getattr(self, "_runtime_ready", True):
            message = (
                f"运行中 ADB 操作失败: {action_name}; serial={serial}; "
                "已停止主链，未执行运行中重连"
            )
        else:
            message = f"ADB 启动阶段操作失败: {action_name}; serial={serial}"
        return RuntimeError(message)

    def _run_with_retry(self, action_name: str, operation):
        """在当前设备对象上做最小短重试，不做运行中重连。"""
        last_exc: Exception | None = None
        for attempt in range(1, self.operation_retry_count + 1):
            try:
                return operation()
            except Exception as exc:  # pragma: no cover - 依赖真实 adb 环境
                last_exc = exc
                if not self._is_retryable_error(exc) or attempt >= self.operation_retry_count:
                    raise self._wrap_operation_error(action_name, exc) from exc
                log.warning(
                    "%s failed on current adb device serial=%s (%s/%s): %s",
                    action_name,
                    getattr(self, "_device_serial", getattr(self.device, "serial", "unknown")),
                    attempt,
                    self.operation_retry_count,
                    exc,
                )
                time.sleep(self.operation_retry_delay)
        if last_exc is not None:
            raise self._wrap_operation_error(action_name, last_exc) from last_exc

    def click(self, x: int, y: int) -> None:
        """按 profile 坐标点击。"""
        self._run_with_retry("click", lambda: self.device.click(x, y))

    def click_raw(self, x: int, y: int) -> None:
        """按设备真实坐标点击，通常用于模板匹配返回的位置。"""
        self._run_with_retry("click_raw", lambda: self.device.click(x, y))

    def click_region(self, region: tuple[int, int, int, int]) -> None:
        """点击矩形区域的中心点。"""
        x1, y1, x2, y2 = region
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        self.click(cx, cy)

    def screenshot(self, save_path: str) -> str:
        """截图后保存，返回保存后的路径。"""
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        image: Image.Image = self._run_with_retry("screenshot", self._capture_screenshot)
        image.save(save_path)
        return save_path

    def screenshot_array(self, save_path: Optional[str] = None) -> Image.Image:
        """截图；可选保存到磁盘。"""
        image: Image.Image = self._run_with_retry("screenshot", self._capture_screenshot)
        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            image.save(save_path)
        return image

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        """按 profile 坐标执行滑动。"""
        self._run_with_retry("swipe", lambda: self.device.swipe(x1, y1, x2, y2, duration))

    @property
    def resolution(self) -> tuple[int, int]:
        """返回横屏方向下的设备分辨率。"""
        w, h = self._read_resolution()
        return (w, h) if w > h else (h, w)

    @property
    def serial(self) -> str:
        """返回当前连接设备的序列号。"""
        return self.device.serial

    def _capture_screenshot(self) -> Image.Image:
        """使用短超时 screencap 截图，避免底层连接长期挂住。"""
        png_bytes = self.device.shell(
            ["screencap", "-p"],
            encoding=None,
            timeout=getattr(self, "screenshot_timeout", DEFAULT_SCREENSHOT_TIMEOUT),
        )
        image = Image.open(io.BytesIO(png_bytes))
        image.load()
        if image.mode == "RGBA":
            image = image.convert("RGB")
        return image
