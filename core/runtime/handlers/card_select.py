"""选卡页处理器。"""

from __future__ import annotations

import logging

from core.battle_runtime import build_command_card_plan
from core.command_card_recognition import CommandCardInfo, CommandCardPrediction
from core.perception.battle_ocr import ServantNpStatus
from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameCoordinates, GameState

log = logging.getLogger("core.runtime.handlers.card_select")


class CardSelectHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        if not self.waiter.confirm_state_entry(GameState.CARD_SELECT):
            log.warning("普通指令卡区域在超时内未稳定，已按当前画面继续识别")
        np_statuses = self._read_np_statuses_with_retry()
        cards, prediction = self._read_command_cards()
        card_owners = (
            {card.index: card.owner for card in cards}
            if cards is not None
            else self._read_command_card_owners()
        )
        if prediction is not None and prediction.has_low_confidence:
            low_cards = ", ".join(
                str(trace.index) for trace in prediction.low_confidence_traces
            )
            reason_parts: list[str] = []
            if low_cards:
                reason_parts.append(f"卡位：{low_cards}")
            if prediction.joint_low_confidence:
                reason_parts.append("整手联合分差不足")
            reason_text = "；".join(reason_parts) if reason_parts else "无可用联合结果"
            raise RuntimeError(
                f"普通指令卡识别低置信度，已停止运行等待人工确认。{reason_text}"
            )
        card_plan = self.build_card_plan(np_statuses, card_owners, cards)
        self.execute_card_plan(card_plan)
        self._wait_after_card_plan()

    def _read_np_statuses_with_retry(self) -> list[ServantNpStatus]:
        statuses = self.session.read_np_statuses()
        if self.session.config.ocr.retry_once_on_low_confidence and any(
            not status.success for status in statuses
        ):
            log.info("检测到 NP OCR 结果不稳定，已刷新一次重读")
            self.session.refresh_screen()
            statuses = self.session.read_np_statuses()
        return statuses

    def build_card_plan(
        self,
        np_statuses: list[ServantNpStatus],
        card_owners: dict[int, str | None] | None = None,
        cards: list[CommandCardInfo] | None = None,
    ) -> list[dict[str, int]]:
        noble_indices = [
            status.servant_index for status in np_statuses if status.is_ready
        ]
        servant_priority = self.session.command_card_priority()
        if card_owners is None:
            card_owners = {}
        plan = build_command_card_plan(
            noble_indices=noble_indices,
            card_owners=card_owners,
            servant_priority=servant_priority,
            cards=cards,
            support_attacker=self.session.support_attacker_servant_name(),
        )
        log.info("本回合出卡计划：%s", plan)
        return plan[:3]

    def execute_card_plan(self, card_plan: list[dict[str, int]]) -> None:
        for action in card_plan:
            if action["type"] == "noble":
                self._select_noble_card_with_optional_target(action["index"])
                continue
            self.session.adb.click(*GameCoordinates.CARD_POSITIONS[action["index"]])
            self.waiter.wait_seconds("已点击普通指令卡", 0.3)
        log.info("已执行出卡计划：%s", card_plan)

    def _wait_after_card_plan(self) -> None:
        self.waiter.wait_seconds("已完成出卡，等待战斗动画起步", 3.0)
        detection = self.waiter.wait_state_exit(
            {GameState.CARD_SELECT, GameState.UNKNOWN},
            timeout=max(0.0, 20.0 - 3.0),
            poll_interval=1.0,
        )
        if detection is not None:
            log.info("战斗动画结束，当前已切换到 %s", detection.state.name)
            return
        log.warning("战斗动画等待超时，继续后续流程")

    def _select_noble_card_with_optional_target(self, servant_index: int) -> None:
        self.session.battle.select_noble_card(servant_index)
        self.session.refresh_screen()
        target_select_pos = self.session.recognizer.match(
            self.session.resources.template("skill_select_servent.png", category="battle"),
            self.session.get_latest_screen_image(),
        )
        if target_select_pos:
            self.session.battle.select_servant_target(1)
            log.info("宝具 servant=%s 触发目标选择，默认选择第一个从者", servant_index)
            return
        log.info("宝具 servant=%s 已加入本回合出卡", servant_index)

    def _read_command_card_owners(self) -> dict[int, str | None] | None:
        servant_priority = self.session.command_card_priority()
        frontline_servants = self.session.frontline_servant_names()
        if not servant_priority or not frontline_servants:
            return None
        try:
            owners = self.session.get_command_card_recognizer().recognize_frontline(
                self.session.get_latest_screen_rgb(),
                frontline_servants,
                support_attacker=self.session.support_attacker_servant_name(),
            )
        except Exception as exc:
            log.warning("普通指令卡识别失败，已回退默认出卡：%s", exc)
            return None
        log.info("普通指令卡归属识别：%s", owners)
        return owners

    def _read_command_cards(
        self,
    ) -> tuple[list[CommandCardInfo] | None, CommandCardPrediction | None]:
        servant_priority = self.session.command_card_priority()
        frontline_servants = self.session.frontline_servant_names()
        if not servant_priority or not frontline_servants:
            return None, None
        try:
            screen_rgb = self.session.get_latest_screen_rgb()
            prediction = self.session.get_command_card_recognizer().analyze_frontline(
                screen_rgb,
                frontline_servants,
                support_attacker=self.session.support_attacker_servant_name(),
            )
            image_path, masked_path, json_path = self.session.save_command_card_evidence(
                prediction,
                screen_rgb,
            )
            cards = prediction.cards
        except Exception as exc:
            log.warning("普通指令卡识别失败，已回退默认出卡：%s", exc)
            return None, None
        log.info(
            "普通指令卡识别证据：image=%s masked=%s json=%s",
            image_path,
            masked_path,
            json_path,
        )
        log.info(
            "普通指令卡识别：%s",
            [
                {"index": card.index, "owner": card.owner, "color": card.color}
                for card in cards
            ],
        )
        return cards, prediction
