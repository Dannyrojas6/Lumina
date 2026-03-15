import logging
from pathlib import Path
import subprocess
import shutil
import platform
from adbutils import adb, AdbDevice
from typing import Optional

log = logging.getLogger("core.adb_controller")


def find_adb_path() -> str:
    in_path = shutil.which("adb")
    if in_path:
        log.debug(f"use system adb: {in_path}")
        return in_path

    fallbacks = {
        "Windows": [
            r"C:\Users\kk\scoop\apps\adb\current\platform-tools\adb.exe",
            r"C:\platform-tools\adb.exe",
        ],
        "Linux": "/usr/bin/adb",
    }
    system = platform.system()
    for path in fallbacks.get(system, []):
        if Path(path).exists():
            log.debug(f"use fallback adb: {path}")
            return path
    raise FileNotFoundError(
        "can't find adb! please check adb path or install adb tools."
    )


def start_adb_server(adb_path: Optional[str] = None) -> None:
    path = adb_path or find_adb_path()
    subprocess.run([path, "start-server"], check=False, capture_output=True)
    log.info("ADB Server is activated")


class AdbController:
    BASE_W: int = 1920
    BASE_H: int = 1080

    def __init__(self, serial: Optional[str] = None) -> None:
        start_adb_server()
        self.device: AdbDevice = self._connect(serial)
        self._scale_x, self._scale_y = self._calc_scale()

    def _connect(self, serial: Optional[str]) -> AdbDevice:
        if serial:
            log.info(f"connected device: {serial}")
            return adb.device(serial=serial)
        return self._select_device()

    def _select_device(self) -> AdbDevice:
        devices = adb.device_list()
        serials = [device.serial for device in devices]
        if not serials:
            raise RuntimeError("can't find adb device!please try again.")
        if len(serials) == 1:
            log.info(f"connect unique device: {serials[0]}")
            return adb.device(serial=serials[0])
        for i, value in enumerate(serials, 1):
            print(f"{i}: {value}")
        idx = int(input("please enter device number: ")) - 1
        return adb.device(serial=serials[idx])

    def _calc_scale(self) -> tuple[float, float]:
        info = self.device.info
        w = info["display"]["weight"]
        h = info["display"]["height"]

        if w < h:
            w, h = h, w
        scale_x = w / self.BASE_W
        scale_y = h / self.BASE_H
        log.info(f"current resolution: {w}x{h}")
        log.info(f"scale ratio: x={scale_x:.3f} y={scale_y:.3f}")
        return scale_x, scale_y

    def _scale(self, x: int, y: int) -> tuple[int, int]:
        return int(x * self._scale_x), int(y * self._scale_y)

    def click(self, x: int, y: int) -> None:
        sx, sy = self._scale(x, y)
        self.device.click(sx, sy)
        log.debug(f"click ({x},{y}) -> scaled ({sx},{sy})")

    def click_raw(self, x: int, y: int) -> None:
        self.device.click(x, y)
        log.debug(f"clicl_raw ({x},{y})")

    def click_region(self, region: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = region
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        self.click(cx, cy)

    def screenshot(self, save_path: str) -> str:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        self.device.screenshot().save(save_path)
        log.debug(f"screenshot: {save_path}")
        return save_path

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        sx1, sy1 = self._scale(x1, y1)
        sx2, sy2 = self._scale(x2, y2)
        self.device.swipe(sx1, sy1, sx2, sy2, duration)
        log.debug(f"swipe ({x1},{y1}->{x2},{y2})")

    @property
    def resolution(self) -> tuple[int, int]:
        info = self.device.info
        w, h = info["display"]["width"], info["display"]["height"]
        return (w, h) if w > h else (h, w)

    @property
    def serial(self) -> str:
        return self.device.serial
