"""战斗执行相关流程。"""

from __future__ import annotations

import logging
import time
from typing import Optional

from core.battle_runtime.command_card_recognition import (
    CommandCardInfo,
    CommandCardRecognizer,
    choose_best_card_chain,
)
from core.battle_runtime.planner_models import BattleSnapshot as SmartBattleSnapshot
from core.shared import GameCoordinates, GameState
from core.perception.battle_ocr import ServantNpStatus

log = logging.getLogger("core.battle_flow")


def build_command_card_plan(
    *,
    noble_indices: list[int],
    card_owners: dict[int, str | None],
    servant_priority: list[str],
    cards: Optional[list[CommandCardInfo]] = None,
    support_attacker: str | None = None,
) -> list[dict[str, int]]:
    """按宝具优先和从者优先顺序构建统一出卡计划。"""
    plan: list[dict[str, int]] = [
        {"type": "noble", "index": servant_index}
        for servant_index in noble_indices[:3]
    ]
    if len(plan) >= 3:
        return plan[:3]

    remaining_cards = [index for index in (1, 2, 3, 4, 5)]
    used_cards: set[int] = set()
    normalized_priority = [
        str(item).replace("\\", "/").strip().strip("/")
        for item in servant_priority
        if str(item).strip()
    ]
    if cards:
        best_chain = choose_best_card_chain(
            cards=sorted(cards, key=lambda item: item.index),
            servant_priority=normalized_priority,
            support_attacker=support_attacker,
        )
        for card in best_chain:
            if len(plan) >= 3:
                return plan[:3]
            if card.index in used_cards:
                continue
            plan.append({"type": "card", "index": card.index})
            used_cards.add(card.index)

    for servant_name in normalized_priority:
        for card_index in remaining_cards:
            if len(plan) >= 3:
                return plan[:3]
            if card_index in used_cards:
                continue
            if card_owners.get(card_index) != servant_name:
                continue
            plan.append({"type": "card", "index": card_index})
            used_cards.add(card_index)

    for card_index in remaining_cards:
        if len(plan) >= 3:
            break
        if card_index in used_cards:
            continue
        plan.append({"type": "card", "index": card_index})
        used_cards.add(card_index)
    return plan[:3]


class BattleFlowMixin:
    """承载战斗中技能、出卡、OCR 和结算逻辑。"""

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
        cards = self._read_command_cards()
        card_owners = (
            {card.index: card.owner for card in cards}
            if cards is not None
            else self._read_command_card_owners()
        )
        card_plan = self.build_card_plan(np_statuses, card_owners, cards)
        self.execute_card_plan(card_plan)
        self._wait_after_card_plan()

    def _wait_after_card_plan(self) -> None:
        """出卡后先给动画最短缓冲，再等待画面离开选卡界面。"""
        self._sleep_with_log(self.POST_CARD_MIN_WAIT, "已完成出卡，等待战斗动画起步")
        deadline = time.time() + max(0.0, self.BATTLE_ANIMATION_WAIT - self.POST_CARD_MIN_WAIT)
        while time.time() < deadline:
            detection = self.state_detector.detect()
            if detection.state not in (GameState.CARD_SELECT, GameState.UNKNOWN):
                log.info("战斗动画结束，当前已切换到 %s", detection.state.name)
                return
            time.sleep(self.POST_CARD_POLL_INTERVAL)
        log.warning("战斗动画等待超时，继续后续流程")

    def handle_battle_result(self) -> None:
        """处理结算界面，并按模板完成收尾点击。"""
        self._loop_done += 1
        self._battle_actions_done = False
        self._used_servant_skills.clear()
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
            log.info(
                "当前回合=%s 已执行过智能判断，本次跳过重复释放", snapshot.current_turn
            )
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
        if wave_index is not None:
            wave_known = True
            self._last_wave_index = wave_index
        elif self._last_wave_index is not None:
            wave_index = self._last_wave_index
            log.warning("波次 OCR 缺失，已沿用上次确认波次=%s", wave_index)

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
        self,
        np_statuses: list[ServantNpStatus],
        card_owners: Optional[dict[int, str | None]] = None,
        cards: Optional[list[CommandCardInfo]] = None,
    ) -> list[dict[str, int]]:
        """构建本回合的出卡计划，优先宝具，其次固定普通指令卡。"""
        noble_indices = [
            status.servant_index for status in np_statuses if status.is_ready
        ]
        servant_priority = self._command_card_priority()
        if card_owners is None:
            card_owners = {}
        plan = build_command_card_plan(
            noble_indices=noble_indices,
            card_owners=card_owners,
            servant_priority=servant_priority,
            cards=cards,
            support_attacker=self._support_attacker_servant_name(),
        )
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

    def _command_card_priority(self) -> list[str]:
        """返回当前普通卡从者优先顺序。"""
        raw_priority = getattr(
            self.config.smart_battle,
            "command_card_priority",
            [],
        )
        return [
            str(item).replace("\\", "/").strip().strip("/")
            for item in raw_priority
            if str(item).strip()
        ]

    def _frontline_servant_names(self) -> list[str]:
        """返回前排三人的完整从者标识。"""
        return [
            str(slot.servant).replace("\\", "/").strip().strip("/")
            for slot in self.config.smart_battle.frontline
            if str(slot.servant).strip()
        ]

    def _read_command_card_owners(self) -> Optional[dict[int, str | None]]:
        """识别五张普通指令卡分别属于谁。"""
        servant_priority = self._command_card_priority()
        frontline_servants = self._frontline_servant_names()
        if not servant_priority or not frontline_servants:
            return None
        if self._command_card_recognizer is None:
            self._command_card_recognizer = CommandCardRecognizer(self.resources)
        try:
            owners = self._command_card_recognizer.recognize_frontline(
                self._get_latest_screen_rgb(),
                frontline_servants,
            )
        except Exception as exc:
            log.warning("普通指令卡识别失败，已回退默认出卡：%s", exc)
            return None
        log.info("普通指令卡归属识别：%s", owners)
        return owners

    def _read_command_cards(self) -> Optional[list[CommandCardInfo]]:
        """识别五张普通卡的归属和颜色。"""
        servant_priority = self._command_card_priority()
        frontline_servants = self._frontline_servant_names()
        if not servant_priority or not frontline_servants:
            return None
        if self._command_card_recognizer is None:
            self._command_card_recognizer = CommandCardRecognizer(self.resources)
        try:
            cards = self._command_card_recognizer.recognize_frontline_cards(
                self._get_latest_screen_rgb(),
                frontline_servants,
            )
        except Exception as exc:
            log.warning("普通指令卡识别失败，已回退默认出卡：%s", exc)
            return None
        log.info(
            "普通指令卡识别：%s",
            [
                {"index": card.index, "owner": card.owner, "color": card.color}
                for card in cards
            ],
        )
        return cards

    def _support_attacker_servant_name(self) -> str | None:
        """返回助战打手的从者标识。"""
        for slot in self.config.smart_battle.frontline:
            if slot.is_support and slot.role == "attacker":
                return str(slot.servant).replace("\\", "/").strip().strip("/")
        return None
