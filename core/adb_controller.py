"""ADB 设备适配层，负责连接设备和执行基础触控。"""

import logging
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from adbutils import AdbDevice, adb
from PIL import Image

log = logging.getLogger("core.adb_controller")


def find_adb_path() -> str:
    """优先从 PATH 查找 adb，不存在时再使用平台回退路径。"""
    in_path = shutil.which("adb")
    if in_path:
        log.debug(f"use system adb: {in_path}")
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
            log.debug(f"use fallback adb: {path}")
            return path
    raise FileNotFoundError(
        "can't find adb! please check adb path or install adb tools."
    )


def start_adb_server(adb_path: Optional[str] = None) -> None:
    """启动 adb server；如果已经启动，命令会安全返回。"""
    path = adb_path or find_adb_path()
    subprocess.run([path, "start-server"], check=False, capture_output=True)
    log.info("ADB Server is activated")


class AdbController:
    """对 `adbutils` 做一层封装，统一坐标缩放和截图输出。"""

    BASE_W: int = 1920
    BASE_H: int = 1080
    DEVICE_DISCOVERY_TIMEOUT: float = 8.0
    DEVICE_DISCOVERY_INTERVAL: float = 0.5

    def __init__(self, serial: Optional[str] = None) -> None:
        start_adb_server()
        self.device: AdbDevice = self._connect(serial)
        self._scale_x, self._scale_y = self._calc_scale()

    def _connect(self, serial: Optional[str]) -> AdbDevice:
        """按指定序列号或交互方式选择目标设备。"""
        if serial:
            log.info(f"connected device: {serial}")
            return adb.device(serial=serial)
        return self._select_device()

    def _select_device(self) -> AdbDevice:
        """从已连接设备中选择一台进行后续操作。"""
        deadline = time.time() + self.DEVICE_DISCOVERY_TIMEOUT
        serials: list[str] = []
        while time.time() < deadline:
            devices = adb.device_list()
            serials = [device.serial for device in devices]
            if serials:
                break
            time.sleep(self.DEVICE_DISCOVERY_INTERVAL)
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
        """读取设备分辨率并计算相对 1920x1080 的缩放比例。"""
        w, h = self._read_resolution()

        if w < h:
            w, h = h, w
        scale_x = w / self.BASE_W
        scale_y = h / self.BASE_H
        log.info(f"current resolution: {w}x{h}")
        log.info(f"scale ratio: x={scale_x:.3f} y={scale_y:.3f}")
        return scale_x, scale_y

    def _read_resolution(self) -> tuple[int, int]:
        """尽量从稳定来源读取设备分辨率。"""
        wm_size = self.device.shell("wm size")
        matched = re.search(r"(\d+)x(\d+)", wm_size)
        if matched:
            return int(matched.group(1)), int(matched.group(2))

        info = self.device.info
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

    def _scale(self, x: int, y: int) -> tuple[int, int]:
        """将基准分辨率坐标转换为当前设备的真实坐标。"""
        return int(x * self._scale_x), int(y * self._scale_y)

    def click(self, x: int, y: int) -> None:
        """按基准分辨率坐标点击。"""
        sx, sy = self._scale(x, y)
        self.device.click(sx, sy)
        log.debug(f"click ({x},{y}) -> scaled ({sx},{sy})")

    def click_raw(self, x: int, y: int) -> None:
        """按设备真实坐标点击，通常用于模板匹配返回的位置。"""
        self.device.click(x, y)
        log.debug(f"click_raw ({x},{y})")

    def click_region(self, region: tuple[int, int, int, int]) -> None:
        """点击矩形区域的中心点。"""
        x1, y1, x2, y2 = region
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        self.click(cx, cy)

    def screenshot(self, save_path: str) -> str:
        """截图并归一化到基准分辨率后保存，返回保存后的路径。"""
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        image: Image.Image = self.device.screenshot()
        if image.size != (self.BASE_W, self.BASE_H):
            image = image.resize((self.BASE_W, self.BASE_H))
        image.save(save_path)
        log.debug(f"screenshot: {save_path}")
        return save_path

    def screenshot_array(self, save_path: Optional[str] = None) -> "Image.Image":
        """截图并归一化到基准分辨率；可选保存到磁盘。"""
        image: Image.Image = self.device.screenshot()
        if image.size != (self.BASE_W, self.BASE_H):
            image = image.resize((self.BASE_W, self.BASE_H))
        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            image.save(save_path)
            log.debug(f"screenshot: {save_path}")
        return image

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        """按基准分辨率坐标执行滑动。"""
        sx1, sy1 = self._scale(x1, y1)
        sx2, sy2 = self._scale(x2, y2)
        self.device.swipe(sx1, sy1, sx2, sy2, duration)
        log.debug(f"swipe ({x1},{y1}->{x2},{y2})")

    @property
    def resolution(self) -> tuple[int, int]:
        """返回横屏方向下的设备分辨率。"""
        w, h = self._read_resolution()
        return (w, h) if w > h else (h, w)

    @property
    def serial(self) -> str:
        """返回当前连接设备的序列号。"""
        return self.device.serial
