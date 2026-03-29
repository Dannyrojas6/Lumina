"""主流程编排层，负责状态机驱动和高层业务步骤。"""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from core.adb_controller import AdbController
from core.battle_actions import BattleAction
from core.battle_ocr import BattleOcrReader, ServantNpStatus
from core.battle_snapshot import BattleSnapshotReader
from core.config import BattleConfig
from core.coordinates import GameCoordinates
from core.game_state import GameState
from core.image_recognizer import ImageRecognizer
from core.resources import ResourceCatalog
from core.smart_battle import BattleSnapshot as SmartBattleSnapshot
from core.smart_battle import SmartBattlePlanner
from core.state_detector import StateDetectionResult, StateDetector

log = logging.getLogger("core.workflow")


class DailyAction:
    """管理一次自动刷本流程的高层状态机。"""

    DEFAULT_CLICK_DELAY = 0.5
    SUPPORT_CLICK_DELAY = 2.0
    SUPPORT_REFRESH_WAIT = 3.0
    LOADING_POLL_INTERVAL = 4.0
    BATTLE_ANIMATION_WAIT = 20.0

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
        self._smart_wave_counter = 0
        self._last_wave_index: Optional[int] = None
        self._last_enemy_count: Optional[int] = None
        self._last_current_turn: Optional[int] = None
        self._last_processed_turn: Optional[int] = None
        self._unknown_snapshot_saved = False
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

    def handle_support_select(self) -> None:
        """处理助战选择界面，支持按职阶筛选并滑动搜索目标从者。"""
        support_cfg = self.config.support_config()
        support_class = str(support_cfg["class_name"])
        servant_name = str(support_cfg["servant"])
        pick_index = int(support_cfg["pick_index"])
        max_scroll_pages = int(support_cfg["max_scroll_pages"])

        self._select_support_class(support_class)

        if servant_name:
            if self._search_and_pick_support(servant_name, max_scroll_pages):
                return

            if self._refresh_support_list():
                if self._search_and_pick_support(servant_name, max_scroll_pages):
                    return

            log.warning(
                "未找到目标助战=%s，刷新后仍未命中，回退到默认助战位",
                servant_name,
            )

        self._fallback_pick_support(pick_index)

    def _search_and_pick_support(
        self, servant_name: str, max_scroll_pages: int
    ) -> bool:
        """搜索目标助战，命中后直接点击。"""
        support_pos = self._find_support_on_current_page(servant_name)
        if support_pos:
            self.adb.click(*support_pos)
            time.sleep(self.SUPPORT_CLICK_DELAY)
            log.info("检测到目标助战=%s，已点击进入", servant_name)
            return True

        for page in range(1, max_scroll_pages + 1):
            self._scroll_support_list()
            support_pos = self._find_support_on_current_page(servant_name)
            if support_pos:
                self.adb.click(*support_pos)
                time.sleep(self.SUPPORT_CLICK_DELAY)
                log.info(
                    "滑动第 %s 页后识别到目标助战=%s，已点击进入",
                    page,
                    servant_name,
                )
                return True

        log.warning(
            "未找到目标助战=%s，已超过最大搜索页数=%s",
            servant_name,
            max_scroll_pages,
        )
        return False

    def _select_support_class(self, support_class: str) -> None:
        """点击助战职阶筛选按钮。"""
        if support_class not in {"all", "berserker"}:
            log.warning(
                "当前仅支持 all / berserker，收到 class=%s，已回退为 all",
                support_class,
            )
            support_class = "all"

        class_template = self.resources.support_class_template(support_class)
        class_pos = self.recognizer.match(
            class_template,
            self._get_latest_screen_image(),
        )
        if class_pos:
            self.adb.click(*class_pos)
            time.sleep(self.SUPPORT_CLICK_DELAY)
            self._refresh_screen()
            log.info("检测到助战选择界面，已切换到职阶=%s", support_class)
            return

        if support_class != "all":
            log.warning(
                "未识别到职阶=%s 的模板按钮，回退尝试 all",
                support_class,
            )
            all_class_pos = self.recognizer.match(
                self.resources.support_class_template("all"),
                self._get_latest_screen_image(),
            )
            if all_class_pos:
                self.adb.click(*all_class_pos)
                time.sleep(self.SUPPORT_CLICK_DELAY)
                self._refresh_screen()
                log.info("已回退到全职阶筛选")
                return
        log.warning("助战页未识别到目标职阶按钮，将继续尝试默认选择")

    def _find_support_on_current_page(
        self, servant_name: str
    ) -> Optional[tuple[int, int]]:
        """在当前页尝试识别目标助战头像模板。"""
        servant_template = self.resources.servant_template(servant_name)
        if not Path(servant_template).exists():
            log.warning("目标助战模板缺失：%s", servant_template)
            return None

        match_result = self.recognizer.match_with_score(
            servant_template,
            self._get_latest_screen_image(),
        )
        if match_result.position:
            log.debug(
                "助战模板命中 servant=%s score=%.2f pos=%s",
                servant_name,
                match_result.score,
                match_result.position,
            )
            return match_result.position

        log.debug(
            "助战模板未命中 servant=%s score=%.2f",
            servant_name,
            match_result.score,
        )
        return None

    def _scroll_support_list(self) -> None:
        """向上滑动助战列表，进入下一页搜索。"""
        self.adb.swipe(
            GameCoordinates.SUPPORT_SCROLL_START[0],
            GameCoordinates.SUPPORT_SCROLL_START[1],
            GameCoordinates.SUPPORT_SCROLL_END[0],
            GameCoordinates.SUPPORT_SCROLL_END[1],
            duration=0.3,
        )
        time.sleep(self.SUPPORT_CLICK_DELAY)
        self._refresh_screen()
        log.info("当前页未命中目标助战，已执行一次助战列表滑动")

    def _refresh_support_list(self) -> bool:
        """点击列表更新并确认，等待助战列表重新加载。"""
        list_update_pos = self.recognizer.match(
            self.resources.template("list_update.png", category="support_select"),
            self._get_latest_screen_image(),
        )
        if not list_update_pos:
            log.warning("未识别到助战列表更新按钮，跳过刷新重试")
            return False

        self.adb.click(*list_update_pos)
        time.sleep(self.DEFAULT_CLICK_DELAY)
        self._refresh_screen()

        yes_pos = self.recognizer.match(
            self.resources.template("yes.png"),
            self._get_latest_screen_image(),
        )
        if not yes_pos:
            log.warning("助战列表更新确认框未识别到“是”按钮，跳过刷新重试")
            return False

        self.adb.click(*yes_pos)
        log.info("已点击助战列表更新，并确认刷新")
        time.sleep(self.SUPPORT_REFRESH_WAIT)
        self._refresh_screen()
        return True

    def _fallback_pick_support(self, pick_index: int) -> None:
        """回退到默认助战位选择，保证流程不中断。"""
        support_pos = GameCoordinates.SUPPORT_POSITIONS.get(pick_index)
        if support_pos is None:
            log.warning("无效助战序号=%s，回退到第 1 位", pick_index)
            support_pos = GameCoordinates.SUPPORT_POSITIONS[1]

        self.adb.click(*support_pos)
        time.sleep(self.SUPPORT_CLICK_DELAY)
        log.info("已回退选择默认助战位=%s", pick_index)

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

    def handle_battle_ready(self) -> None:
        """进入战斗可操作界面后执行一次技能序列并进入攻击流程。"""
        if self._smart_battle_enabled:
            self._run_smart_battle_turn()
            self.battle.attack()
            return

        if not self._battle_actions_done:
            actions = self.config.battle_actions()
            if actions:
                log.info("进入战斗流程，开始释放预设技能")
                for action in actions:
                    self._use_action_with_optional_target(action)
            self._battle_actions_done = True
        else:
            log.info("检测到后续回合，跳过技能释放，直接进入攻击")

        self.battle.attack()

    def handle_card_select(self) -> None:
        """进入选卡界面后优先选择可用宝具，再补普通指令卡。"""
        np_statuses = self._read_np_statuses_with_retry()
        card_plan = self.build_card_plan(np_statuses)
        self.execute_card_plan(card_plan)
        if self._smart_battle_enabled and self._smart_wave_counter < 3:
            self._smart_wave_counter += 1
        time.sleep(self.BATTLE_ANIMATION_WAIT)

    def handle_battle_result(self) -> None:
        """处理结算界面，并按模板完成收尾点击。"""
        self._loop_done += 1
        self._battle_actions_done = False
        self._used_servant_skills.clear()
        self._smart_wave_counter = 0
        self._last_wave_index = None
        self._last_enemy_count = None
        self._last_current_turn = None
        self._last_processed_turn = None
        self._click_template(
            "please_click_game_interface.png", "已点击结算页第一次继续"
        )
        time.sleep(1.0)
        self._refresh_screen()
        self._click_template(
            "please_click_game_interface.png", "已点击结算页第二次继续"
        )
        time.sleep(1.0)
        self._refresh_screen()
        self._click_template("next.png", "已点击结算页下一步")
        time.sleep(1.0)
        log.info("战斗结果处理完成")

    def run(self) -> None:
        """循环识别界面状态，并分派给对应处理器。"""
        log.info("脚本启动，进入主循环")
        max_loops = self.config.loop_count
        while max_loops < 0 or self._loop_done < max_loops:
            detection = self.state_detector.detect()
            self.state = detection.state
            log.debug(f"当前状态：{self.state.name}")
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

    def _use_action_with_optional_target(self, action: dict) -> None:
        """释放技能后检查是否出现目标选择界面，出现则默认选择 1 号目标。"""
        action_type = action["type"]
        skill_num = action["skill"]
        default_target = action.get("target") or 1

        if action_type == "master":
            self.battle.click_master_skill(skill_num)
        else:
            self.battle.click_servant_skill(skill_num)

        self._refresh_screen()
        target_select_pos = self.recognizer.match(
            self.resources.template("skill_select_servent.png", category="battle"),
            self._get_latest_screen_image(),
        )
        if target_select_pos:
            self.battle.select_servant_target(default_target)
            if action_type == "master":
                self.battle.finish_master_skill(skill_num, target=default_target)
                return
            self.battle.finish_servant_skill(skill_num, target=default_target)
            return
        if action_type == "master":
            self.battle.finish_master_skill(skill_num)
            return
        self.battle.finish_servant_skill(skill_num)

    def _read_np_statuses_with_retry(self) -> list[ServantNpStatus]:
        """读取 NP 状态，必要时额外刷新一次重读。"""
        statuses = self._read_np_statuses()
        if self.config.ocr.retry_once_on_low_confidence and any(
            not status.success for status in statuses
        ):
            log.info("检测到 NP OCR 结果不稳定，已刷新一次重读")
            self._refresh_screen()
            statuses = self._read_np_statuses()
        return statuses

    def _run_smart_battle_turn(self) -> None:
        """读取当前战斗快照，并按智能战斗规则执行本回合技能。"""
        if self.battle_snapshot_reader is None or self.smart_battle_planner is None:
            log.warning("智能战斗未完整初始化，已保守继续")
            return

        try:
            if self._smart_wave_counter <= 0:
                self._smart_wave_counter = 1
            raw_snapshot = self.battle_snapshot_reader.read_snapshot(
                self._get_latest_screen_rgb()
            )
            snapshot = self._build_smart_snapshot(raw_snapshot)
            decision = self.smart_battle_planner.decide(snapshot)
        except Exception as exc:
            log.warning("智能战斗识别失败，已保守继续：%s", exc)
            return

        log.info(
            "智能战斗 wave=%s turn=%s enemy=%s reason=%s fallback=%s",
            snapshot.wave_index,
            snapshot.current_turn,
            snapshot.enemy_count,
            decision.reason,
            decision.fallback_used,
        )
        if (
            snapshot.turn_known
            and self._last_processed_turn is not None
            and snapshot.current_turn == self._last_processed_turn
        ):
            log.info("当前回合=%s 已执行过智能判断，本次跳过重复释放", snapshot.current_turn)
            return
        for action in decision.actions:
            self._use_action_with_optional_target(
                {
                    "type": action.action_type,
                    "skill": action.global_skill,
                    "target": action.target,
                }
            )
            self._used_servant_skills.add(action.global_skill)
        if snapshot.turn_known:
            self._last_processed_turn = snapshot.current_turn

    def _build_smart_snapshot(self, raw_snapshot) -> SmartBattleSnapshot:
        """将识别层快照转换成判断层需要的最小结构。"""
        wave_index = raw_snapshot.wave_index
        enemy_count = raw_snapshot.enemy_count
        current_turn = raw_snapshot.current_turn
        attacker_slot = next(
            (
                slot.slot
                for slot in self.config.smart_battle.frontline
                if slot.role == "attacker"
            ),
            None,
        )
        attacker_np_status = next(
            (
                status
                for status in raw_snapshot.frontline_np
                if status.servant_index == attacker_slot
            ),
            None,
        )
        attacker_np_known = bool(attacker_np_status and attacker_np_status.success)

        wave_known = False
        inferred_wave = self._smart_wave_counter if self._smart_wave_counter > 0 else None
        if inferred_wave is not None:
            if wave_index is not None and wave_index != inferred_wave:
                log.warning(
                    "波次 OCR=%s 与当前回合=%s 不一致，已沿用当前回合",
                    wave_index,
                    inferred_wave,
                )
            wave_index = inferred_wave
            wave_known = True
            self._last_wave_index = wave_index
        elif wave_index is not None:
            wave_known = True
            self._last_wave_index = wave_index

        if enemy_count is not None:
            self._last_enemy_count = enemy_count
        if current_turn is not None:
            self._last_current_turn = current_turn

        return SmartBattleSnapshot(
            wave_index=self._last_wave_index or 1,
            enemy_count=self._last_enemy_count or 3,
            current_turn=self._last_current_turn or 1,
            frontline_np={
                status.servant_index: (status.np_value or 0)
                for status in raw_snapshot.frontline_np
            },
            skill_availability={
                slot_index: item.available
                for slot_index, item in raw_snapshot.skill_availability.items()
            },
            used_skills=set(self._used_servant_skills),
            attacker_np_known=attacker_np_known,
            wave_known=wave_known,
            enemy_count_known=enemy_count is not None,
            turn_known=current_turn is not None,
        )

    def _read_np_statuses(self) -> list[ServantNpStatus]:
        """从当前战斗截图中读取三位从者的 NP。"""
        if self.battle_ocr is None:
            raise RuntimeError("BattleOcrReader 未初始化，无法读取 NP。")

        statuses = self.battle_ocr.read_np_statuses(self._get_latest_screen_rgb())
        for status in statuses:
            log.debug(
                "NP OCR servant=%s text=%s value=%s confidence=%.2f ready=%s success=%s",
                status.servant_index,
                status.raw_text,
                status.np_value,
                status.confidence,
                status.is_ready,
                status.success,
            )
        return statuses

    def build_card_plan(
        self, np_statuses: list[ServantNpStatus]
    ) -> list[dict[str, int]]:
        """构建本回合的出卡计划，优先宝具，其次固定普通指令卡。"""
        plan: list[dict[str, int]] = []
        for status in np_statuses:
            if status.is_ready:
                plan.append({"type": "noble", "index": status.servant_index})

        for card_index in (1, 2, 3, 4, 5):
            if len(plan) >= 3:
                break
            plan.append({"type": "card", "index": card_index})

        log.info("本回合出卡计划：%s", plan)
        return plan[:3]

    def execute_card_plan(self, card_plan: list[dict[str, int]]) -> None:
        """执行统一的出卡计划。"""
        for action in card_plan:
            if action["type"] == "noble":
                self._select_noble_card_with_optional_target(action["index"])
                continue
            self.adb.click(*GameCoordinates.CARD_POSITIONS[action["index"]])
            time.sleep(0.3)
        log.info("已执行出卡计划：%s", card_plan)

    def _select_noble_card_with_optional_target(self, servant_index: int) -> None:
        """点击宝具卡，并在需要时默认选择第一个从者作为目标。"""
        self.battle.select_noble_card(servant_index)
        self._refresh_screen()
        target_select_pos = self.recognizer.match(
            self.resources.template("skill_select_servent.png", category="battle"),
            self._get_latest_screen_image(),
        )
        if target_select_pos:
            self.battle.select_servant_target(1)
            log.info("宝具 servant=%s 触发目标选择，默认选择第一个从者", servant_index)
            return
        log.info("宝具 servant=%s 已加入本回合出卡", servant_index)

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
