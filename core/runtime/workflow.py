"""主流程编排层，负责状态机驱动和高层业务步骤。"""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from core.device.adb_controller import AdbController
from core.battle_runtime import (
    BattleAction,
    BattleSnapshotReader,
    CommandCardRecognizer,
    SmartBattlePlanner,
)
from core.runtime.battle_flow import BattleFlowMixin, build_command_card_plan
from core.shared import BattleConfig, GameCoordinates, GameState
from core.perception import BattleOcrReader, ImageRecognizer, StateDetectionResult, StateDetector
from core.shared.resource_catalog import ResourceCatalog
from core.runtime.support_flow import SupportFlowMixin
from core.support_recognition.verifier import SupportPortraitVerifier

log = logging.getLogger("core.workflow")


class DailyAction(SupportFlowMixin, BattleFlowMixin):
    """管理一次自动刷本流程的高层状态机。"""

    DEFAULT_CLICK_DELAY = 0.5
    SUPPORT_CLICK_DELAY = 3.0
    SUPPORT_ENTRY_BUFFER_WAIT = 2.0
    SUPPORT_REFRESH_WAIT = 3.0
    LOADING_POLL_INTERVAL = 4.0
    BATTLE_ANIMATION_WAIT = 20.0
    POST_CARD_MIN_WAIT = 3.0
    POST_CARD_POLL_INTERVAL = 1.0

    def __init__(
        self,
        adb_ctl: AdbController,
        recognizer: ImageRecognizer,
        config: BattleConfig,
        resources: ResourceCatalog,
        battle_ocr: Optional[BattleOcrReader] = None,
        battle_snapshot_reader: Optional[BattleSnapshotReader] = None,
        smart_battle_planner: Optional[SmartBattlePlanner] = None,
    ) -> None:
        self.adb = adb_ctl
        self.recognizer = recognizer
        self.battle = BattleAction(
            adb_ctl,
            skill_interval=config.skill_interval,
            skill_pre_skip_delay=config.skill_pre_skip_delay,
            master_skill_open_delay=config.master_skill_open_delay,
        )
        self.config = config
        self.resources = resources
        self.battle_ocr = battle_ocr
        self.battle_snapshot_reader = battle_snapshot_reader
        self.smart_battle_planner = smart_battle_planner
        self._smart_battle_enabled = bool(
            config.smart_battle.enabled
            and battle_snapshot_reader is not None
            and smart_battle_planner is not None
        )
        self.state = GameState.UNKNOWN
        self.state_detector = StateDetector(
            recognizer=recognizer,
            screen_callback=self._refresh_screen,
            resources=resources,
            screen_array_callback=self._get_latest_screen_image,
        )
        self.handlers: dict[GameState, Callable[[], None]] = {
            GameState.MAIN_MENU: self.handle_stage_select,
            GameState.SUPPORT_SELECT: self.handle_support_select,
            GameState.TEAM_CONFIRM: self.handle_team_confirm,
            GameState.LOADING_TIPS: self.handle_loading_tips,
            GameState.DIALOG: self.handle_dialog,
            GameState.BATTLE_READY: self.handle_battle_ready,
            GameState.CARD_SELECT: self.handle_card_select,
            GameState.BATTLE_RESULT: self.handle_battle_result,
        }
        self._latest_screen_image: Optional[np.ndarray] = None
        self._latest_screen_rgb: Optional[np.ndarray] = None
        self._loop_done = 0
        self._battle_actions_done = False
        self._used_servant_skills: set[int] = set()
        self._last_wave_index: Optional[int] = None
        self._last_enemy_count: Optional[int] = None
        self._last_current_turn: Optional[int] = None
        self._last_processed_turn: Optional[int] = None
        self._unknown_snapshot_saved = False
        self._support_verifiers: dict[str, SupportPortraitVerifier] = {}
        self._command_card_recognizer: Optional[CommandCardRecognizer] = None
        self._unknown_fallback_templates = [
            ("close_upper_left.png", "未知状态兜底：已点击左上角关闭"),
            ("close.png", "未知状态兜底：已点击关闭"),
            ("next.png", "未知状态兜底：已点击下一步"),
            ("no.png", "未知状态兜底：已点击否"),
            ("yes.png", "未知状态兜底：已点击是"),
            ("click_screen.png", "未知状态兜底：已点击屏幕"),
            (
                "please_click_game_interface.png",
                "未知状态兜底：已点击请点击游戏界面",
            ),
        ]

    def handle_stage_select(self) -> None:
        """在主菜单阶段点击固定关卡入口，开始一次刷本流程。"""
        quest_slot = self.config.quest_slot
        quest_pos = GameCoordinates.QUEST_SLOTS.get(quest_slot)
        if quest_pos is None:
            log.warning("无效关卡槽位=%s，回退到第 1 个关卡入口", quest_slot)
            quest_pos = GameCoordinates.QUEST_SLOTS[1]
        self.adb.click(*quest_pos)
        time.sleep(self.DEFAULT_CLICK_DELAY)
        log.info("检测到主菜单，已点击第 %s 个关卡入口", quest_slot)

    def _refresh_screen(self) -> str:
        """更新当前截图文件并返回其路径。"""
        save_path = (
            self.resources.screen_path if self.config.save_debug_screenshots else None
        )
        image = self.adb.screenshot_array(save_path)
        self._latest_screen_rgb = np.array(image)
        self._latest_screen_image = cv2.cvtColor(
            self._latest_screen_rgb, cv2.COLOR_RGB2GRAY
        )
        return self.resources.screen_path

    def _sleep_with_log(self, seconds: float, message: str) -> None:
        """对较长等待补一条明确日志，避免误判为卡死。"""
        log.info("%s，等待 %.1f 秒", message, seconds)
        time.sleep(seconds)

    def _get_latest_screen_image(self) -> np.ndarray:
        """返回最近一次刷新的灰度截图。"""
        if self._latest_screen_image is None:
            self._refresh_screen()
        return self._latest_screen_image

    def _get_latest_screen_rgb(self) -> np.ndarray:
        """返回最近一次刷新的 RGB 截图。"""
        if self._latest_screen_rgb is None:
            self._refresh_screen()
        return self._latest_screen_rgb

    def _save_unknown_snapshot(self) -> Optional[str]:
        """将当前未识别截图落盘，便于排查识别失败原因。"""
        if self._latest_screen_rgb is None:
            return None

        screenshot_dir = Path(self.resources.screen_path).parent / "unknown"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_path = screenshot_dir / f"unknown_{timestamp}.png"
        cv2.imwrite(
            str(save_path), cv2.cvtColor(self._latest_screen_rgb, cv2.COLOR_RGB2BGR)
        )
        return str(save_path)

    def handle_dialog(self) -> None:
        """处理剧情跳过和确认弹窗。"""
        pos = self.recognizer.match(
            self.resources.template("skip.png"),
            self._get_latest_screen_image(),
        )
        if pos:
            self.adb.click(*pos)
            time.sleep(self.DEFAULT_CLICK_DELAY)
            self._refresh_screen()
            yes_pos = self.recognizer.match(
                self.resources.template("yes.png"),
                self._get_latest_screen_image(),
            )
            if yes_pos:
                self.adb.click(*yes_pos)
                time.sleep(self.DEFAULT_CLICK_DELAY)
            log.info("跳过对话")

    def handle_team_confirm(self) -> None:
        """处理队伍确认界面，并点击开始任务。"""
        start_pos = self.recognizer.match(
            self.resources.template("start_task.png", category="team_confirm"),
            self._get_latest_screen_image(),
        )
        if start_pos:
            self.adb.click(*start_pos)
            time.sleep(self.DEFAULT_CLICK_DELAY)
            log.info("检测到队伍确认界面，已点击开始任务")

    def handle_loading_tips(self) -> None:
        """等待关卡加载提示消失，并为正式进入战斗预留缓冲时间。"""
        log.info("检测到加载提示，等待其消失")
        tips_template = self.resources.template("tips.png", category="battle")
        while self.recognizer.match(tips_template, self._get_latest_screen_image()):
            time.sleep(self.LOADING_POLL_INTERVAL)
            self._refresh_screen()
        log.info("加载提示已消失，额外等待 3s 进入战斗")
        time.sleep(3.0)

    def run(self) -> None:
        """循环识别界面状态，并分派给对应处理器。"""
        log.info("脚本启动，进入主循环")
        max_loops = self.config.loop_count
        while max_loops < 0 or self._loop_done < max_loops:
            detection = self.state_detector.detect()
            self.state = detection.state
            log.debug("当前状态：%s", self.state.name)
            handler = self.handlers.get(self.state)
            if handler is None:
                self._log_unhandled_state(detection)
                time.sleep(1.0)
                continue
            handler()

    def _log_unhandled_state(self, detection: StateDetectionResult) -> None:
        """输出未处理状态的诊断信息，便于区分正常等待和识别故障。"""
        missing_count = len(detection.missing_templates)
        if detection.state == GameState.UNKNOWN:
            if self._handle_unknown_fallback():
                self._unknown_snapshot_saved = False
                time.sleep(1.0)
                return
            snapshot_path = None
            if not self._unknown_snapshot_saved:
                snapshot_path = self._save_unknown_snapshot()
                self._unknown_snapshot_saved = True
            if detection.best_match_state is not None:
                log.warning(
                    "未识别到已建模状态，最佳候选=%s score=%.2f template=%s screenshot=%s "
                    "missing_templates=%d unknown_snapshot=%s，等待1s后重试",
                    detection.best_match_state.name,
                    detection.best_score,
                    detection.matched_template,
                    detection.screen_path,
                    missing_count,
                    snapshot_path,
                )
                return
            log.warning(
                "状态识别失败，未找到可用模板匹配 screenshot=%s missing_templates=%d "
                "unknown_snapshot=%s，等待1s后重试",
                detection.screen_path,
                missing_count,
                snapshot_path,
            )
            return

        self._unknown_snapshot_saved = False
        log.warning(
            "检测到未处理状态=%s screenshot=%s，等待1s后重试",
            detection.state.name,
            detection.screen_path,
        )

    def _handle_unknown_fallback(self) -> bool:
        """在未知状态下尝试点击常见通用按钮，避免流程卡死。"""
        for template_name, message in self._unknown_fallback_templates:
            if self._click_template(template_name, message):
                return True
        return False

    def _click_template(self, template_name: str, success_message: str) -> bool:
        """在当前截图中匹配模板并点击。"""
        pos = self.recognizer.match(
            self.resources.template(template_name),
            self._get_latest_screen_image(),
        )
        if pos:
            self.adb.click(*pos)
            time.sleep(self.DEFAULT_CLICK_DELAY)
            log.info(success_message)
            return True
        return False
