"""
FGO 自动化脚本 - 重构版
架构分层：
  GameCoordinates  → 所有坐标/区域常量
  AdbController    → 设备通信（点击、截图）
  ImageRecognizer  → 图像识别（模板匹配）
  BattleAction     → 战斗原子操作（技能、攻击）
  DailyAction      → 高层流程（状态机驱动）
"""

import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

import cv2
import yaml
from adbutils import adb

# ─────────────────────────────────────────────
# 日志配置
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fgo_bot")


# ─────────────────────────────────────────────
# 1. 坐标常量（统一管理）
# ─────────────────────────────────────────────
class GameCoordinates:
    # 从者技能点击坐标（中心点）
    SERVANT_SKILLS: dict[int, tuple[int, int]] = {
        1: (110, 880),
        2: (243, 880),
        3: (376, 880),
        4: (585, 880),
        5: (718, 880),
        6: (850, 880),
        7: (1060, 880),
        8: (1200, 880),
        9: (1324, 880),
    }
    # 技能区域（用于截图识别，左上x, 左上y, 右下x, 右下y）
    SERVANT_SKILL_REGIONS: dict[str, tuple[int, int, int, int]] = {
        "s1_1": (58, 812, 162, 921),
        "s1_2": (191, 816, 292, 920),
        "s1_3": (322, 810, 427, 922),
        "s2_1": (532, 811, 640, 922),
        "s2_2": (665, 811, 773, 923),
        "s2_3": (800, 810, 904, 923),
        "s3_1": (1011, 812, 1116, 923),
        "s3_2": (1144, 812, 1249, 923),
        "s3_3": (1277, 812, 1382, 923),
    }
    # 其他关键坐标/区域
    SKILL_SELECT_SERVANT: tuple = (849, 262, 1077, 314)
    ATTACK_BUTTON: tuple = (1600, 800, 1806, 1013)
    FIGHT_MENU: tuple = (1700, 220, 1882, 389)
    MASTER_SKILL: tuple = (1699, 379, 1885, 557)
    SPEED_SKIP: tuple = (1849, 651)

    @staticmethod
    def region_center(region: tuple[int, int, int, int]) -> tuple[int, int]:
        x1, y1, x2, y2 = region
        return (x1 + x2) // 2, (y1 + y2) // 2


# ─────────────────────────────────────────────
# 2. 配置文件（YAML 驱动战斗策略）
# ─────────────────────────────────────────────
@dataclass
class BattleConfig:
    """单次刷本的战斗配置，支持从 YAML 加载"""

    total_waves: int = 3
    loop_count: int = 10  # 刷本次数，-1 表示无限
    skill_sequence: list = field(default_factory=list)  # 每波技能释放顺序
    match_threshold: float = 0.75  # 图像识别阈值

    @classmethod
    def from_yaml(cls, path: str) -> "BattleConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def default(cls) -> "BattleConfig":
        """默认配置：三波全开技能"""
        return cls(
            total_waves=3,
            loop_count=10,
            skill_sequence=[
                {"wave": 1, "skills": [1, 2, 3]},
                {"wave": 2, "skills": [4, 5, 6]},
                {"wave": 3, "skills": [7, 8, 9]},
            ],
        )


# ─────────────────────────────────────────────
# 3. ADB 控制器（只管设备通信）
# ─────────────────────────────────────────────
class AdbController:
    def __init__(self, serial: Optional[str] = None) -> None:
        if serial:
            self.device = adb.device(serial=serial)
        else:
            self.device = self._select_device()

    def _select_device(self):
        devices = adb.device_list()
        serials = [d.serial for d in devices]
        if not serials:
            raise RuntimeError("未找到 ADB 设备，请检查连接。")
        for i, s in enumerate(serials, 1):
            print(f"  {i}: {s}")
        idx = int(input("请输入设备编号：")) - 1
        return adb.device(serial=serials[idx])

    def click(self, x: int, y: int) -> None:
        self.device.click(x, y)

    def click_region(self, region: tuple[int, int, int, int]) -> None:
        cx, cy = GameCoordinates.region_center(region)
        self.click(cx, cy)

    def screenshot(self, save_path: str) -> None:
        self.device.screenshot().save(save_path)
        log.debug(f"截图已保存：{save_path}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        self.device.swipe(x1, y1, x2, y2, duration)


# ─────────────────────────────────────────────
# 4. 图像识别器（只管模板匹配）
# ─────────────────────────────────────────────
class ImageRecognizer:
    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = threshold

    def match(self, template_path: str, screen_path: str) -> Optional[tuple[int, int]]:
        """返回模板在屏幕中的中心坐标，未找到返回 None"""
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        screen = cv2.imread(screen_path, cv2.IMREAD_GRAYSCALE)

        if template is None or screen is None:
            log.warning(f"图像读取失败：{template_path} / {screen_path}")
            return None

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= self.threshold:
            h, w = template.shape
            cx, cy = max_loc[0] + w // 2, max_loc[1] + h // 2
            log.debug(
                f"匹配成功 [{max_val:.2f}]：{Path(template_path).name} → ({cx}, {cy})"
            )
            return cx, cy

        log.debug(f"匹配失败 [{max_val:.2f}]：{Path(template_path).name}")
        return None

    def wait_for(
        self,
        template_path: str,
        screen_callback,
        timeout: float = 30.0,
        interval: float = 1.0,
    ) -> Optional[tuple[int, int]]:
        """
        等待某个模板出现，出现后返回坐标。
        screen_callback: 无参函数，每次调用会刷新截图并返回截图路径。
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            screen_path = screen_callback()
            pos = self.match(template_path, screen_path)
            if pos:
                return pos
            time.sleep(interval)
        log.warning(f"等待超时：{Path(template_path).name}")
        return None


# ─────────────────────────────────────────────
# 5. 战斗原子操作（依赖 AdbController）
# ─────────────────────────────────────────────
class BattleAction:
    def __init__(self, adb_ctl: AdbController) -> None:
        self.adb = adb_ctl
        self.coords = GameCoordinates()

    def use_servant_skill(self, skill_num: int, target: Optional[int] = None) -> None:
        """
        释放从者技能。
        skill_num: 1-9（对应 SERVANT_SKILLS）
        target: 如果技能需要选择目标，传入从者编号 1/2/3
        """
        pos = self.coords.SERVANT_SKILLS[skill_num]
        self.adb.click(*pos)
        time.sleep(0.5)

        if target is not None:
            # 技能目标选择（三个从者的位置，可按需调整）
            target_positions = {1: (430, 600), 2: (720, 600), 3: (1010, 600)}
            self.adb.click(*target_positions[target])
            time.sleep(0.3)

        self.adb.click(*self.coords.SPEED_SKIP)
        log.info(f"技能 {skill_num} 释放完毕")

    def use_master_skill(self, skill_num: int, target: Optional[int] = None) -> None:
        """释放御主技能（1/2/3）"""
        # 先打开御主技能菜单
        self.adb.click_region(self.coords.MASTER_SKILL)
        time.sleep(0.4)
        # 选择具体技能（三个按钮位置按实际截图调整）
        master_skill_pos = {1: (1580, 460), 2: (1715, 460), 3: (1850, 460)}
        self.adb.click(*master_skill_pos[skill_num])
        time.sleep(0.5)
        if target is not None:
            target_positions = {1: (430, 600), 2: (720, 600), 3: (1010, 600)}
            self.adb.click(*target_positions[target])
            time.sleep(0.3)
        log.info(f"御主技能 {skill_num} 释放完毕")

    def attack(self) -> None:
        """点击 ATTACK 进入卡牌选择"""
        self.adb.click_region(self.coords.ATTACK_BUTTON)
        time.sleep(0.5)
        log.info("进入攻击选卡")

    def select_cards(self, card_indices: list[int]) -> None:
        """
        选择指定位置的卡（1-5，从左到右）。
        如不传，默认点击前三张。
        """
        card_positions = {
            1: (290, 650),
            2: (570, 650),
            3: (860, 650),
            4: (1140, 650),
            5: (1420, 650),
        }
        for idx in card_indices[:3]:
            self.adb.click(*card_positions[idx])
            time.sleep(0.3)
        log.info(f"已选卡：{card_indices[:3]}")

    def speed_skip(self) -> None:
        self.adb.click(*self.coords.SPEED_SKIP)


# ─────────────────────────────────────────────
# 6. 游戏状态枚举（状态机）
# ─────────────────────────────────────────────
class GameState(Enum):
    UNKNOWN = auto()
    MAIN_MENU = auto()
    IN_BATTLE = auto()
    WAVE_START = auto()
    CARD_SELECT = auto()
    BATTLE_RESULT = auto()
    DIALOG = auto()


# ─────────────────────────────────────────────
# 7. 高层流程（状态机驱动，依赖下层）
# ─────────────────────────────────────────────
class DailyAction:
    SCREEN_PATH = "test_image/screen.png"
    IMAGE_DIR = "test_image"

    def __init__(
        self,
        adb_ctl: AdbController,
        recognizer: ImageRecognizer,
        config: BattleConfig,
    ) -> None:
        self.adb = adb_ctl
        self.recognizer = recognizer
        self.battle = BattleAction(adb_ctl)
        self.config = config
        self.state = GameState.UNKNOWN
        self._current_wave = 0
        self._loop_done = 0

    # ── 截图工具（给 wait_for 回调用）──────────
    def _refresh_screen(self) -> str:
        self.adb.screenshot(self.SCREEN_PATH)
        return self.SCREEN_PATH

    # ── 状态检测 ───────────────────────────────
    def _detect_state(self) -> GameState:
        self.adb.screenshot(self.SCREEN_PATH)
        checks = {
            GameState.DIALOG: f"{self.IMAGE_DIR}/skip.png",
            GameState.CARD_SELECT: f"{self.IMAGE_DIR}/fight_speed.png",
            GameState.WAVE_START: f"{self.IMAGE_DIR}/fight_menu.png",
            GameState.BATTLE_RESULT: f"{self.IMAGE_DIR}/result.png",
            GameState.MAIN_MENU: f"{self.IMAGE_DIR}/main_menu.png",
        }
        for state, tmpl in checks.items():
            if Path(tmpl).exists():
                if self.recognizer.match(tmpl, self.SCREEN_PATH):
                    return state
        return GameState.UNKNOWN

    # ── 各状态处理 ─────────────────────────────
    def handle_dialog(self) -> None:
        """跳过对话/确认弹窗"""
        pos = self.recognizer.match(f"{self.IMAGE_DIR}/skip.png", self.SCREEN_PATH)
        if pos:
            self.adb.click(*pos)
            time.sleep(0.2)
            # 可能有二次确认
            self.adb.screenshot(self.SCREEN_PATH)
            yes_pos = self.recognizer.match(
                f"{self.IMAGE_DIR}/yes.png", self.SCREEN_PATH
            )
            if yes_pos:
                self.adb.click(*yes_pos)
                time.sleep(0.2)
            log.info("跳过对话")

    def handle_wave_start(self) -> None:
        """波次开始：按配置释放技能"""
        self._current_wave += 1
        log.info(f"===== 第 {self._current_wave} 波 =====")

        skills_this_wave = [
            step["skills"]
            for step in self.config.skill_sequence
            if step["wave"] == self._current_wave
        ]
        if skills_this_wave:
            for skill_num in skills_this_wave[0]:
                self.battle.use_servant_skill(skill_num)
                time.sleep(0.5)

        # 技能释放完毕，点击 ATTACK
        self.battle.attack()

    def handle_card_select(self) -> None:
        """选卡阶段：默认选前三张（可扩展为识别 NP / Buster 优先）"""
        self.battle.select_cards([1, 2, 3])
        time.sleep(1.0)

    def handle_battle_result(self) -> None:
        """战斗结算：点击继续"""
        self._loop_done += 1
        self._current_wave = 0
        # 点击结算画面继续
        self.adb.click(960, 540)
        time.sleep(2)
        self.adb.click(960, 540)
        time.sleep(2)
        self.adb.click(1677, 961)
        time.sleep(2)
        log.info(f"战斗结束，已完成 {self._loop_done} 次")

    # ── 主循环（状态机） ───────────────────────
    def run(self) -> None:
        log.info("脚本启动，进入主循环…")
        max_loops = self.config.loop_count  # -1 为无限
        while max_loops < 0 or self._loop_done < max_loops:
            self.state = self._detect_state()
            log.debug(f"当前状态：{self.state.name}")

            if self.state == GameState.DIALOG:
                self.handle_dialog()
            elif self.state == GameState.WAVE_START:
                self.handle_wave_start()
            elif self.state == GameState.CARD_SELECT:
                self.handle_card_select()
            elif self.state == GameState.BATTLE_RESULT:
                self.handle_battle_result()
            elif self.state == GameState.MAIN_MENU:
                log.info("检测到主界面，任务完成或等待下一次进本")
                break
            else:
                # 状态未知时，等待 1 秒后重试
                log.info("状态未知，等待1s后重试！")
                time.sleep(1.0)


# ─────────────────────────────────────────────
# 8. 入口
# ─────────────────────────────────────────────
def main():
    # 启动 ADB Server
    subprocess.run(
        [r"C:\Users\kk\scoop\apps\adb\current\platform-tools\adb.exe", "start-server"],
        check=False,
    )

    # 尝试从配置文件加载，不存在则用默认配置
    config_path = "battle_config.yaml"
    if Path(config_path).exists():
        config = BattleConfig.from_yaml(config_path)
        log.info(f"已加载配置：{config_path}")
    else:
        config = BattleConfig.default()
        log.info("使用默认配置")

    adb_ctl = AdbController()
    recognizer = ImageRecognizer(threshold=config.match_threshold)
    daily = DailyAction(adb_ctl, recognizer, config)
    daily.run()


if __name__ == "__main__":
    main()
