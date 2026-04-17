"""选卡页处理器。"""

from __future__ import annotations

import logging

from core.battle_runtime import build_command_card_plan
from core.command_card_recognition import (
    CommandCardInfo,
    CommandCardPrediction,
    choose_best_card_chain,
    detect_command_card_color,
)
from core.perception.battle_ocr import ServantNpStatus
from core.runtime.session import RuntimeSession
from core.runtime.waiter import Waiter
from core.shared import GameCoordinates, GameState
from core.shared.config_models import CustomTurnPlan

log = logging.getLogger("core.runtime.handlers.card_select")


class CardSelectHandler:
    def __init__(self, session: RuntimeSession, waiter: Waiter) -> None:
        self.session = session
        self.waiter = waiter

    def handle(self) -> None:
        if not self.waiter.confirm_state_entry(GameState.CARD_SELECT):
            log.warning("普通指令卡区域在超时内未稳定，已按当前画面继续识别")
        np_statuses = self._read_np_statuses_with_retry()
        if getattr(self.session, "custom_sequence_enabled", False):
            card_plan = self._build_custom_sequence_card_plan(np_statuses)
            self.execute_card_plan(card_plan)
            self._wait_after_card_plan()
            return
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
        support_attacker = self.session.support_attacker_servant_name()
        if self.session.smart_battle_enabled:
            plan = self._build_smart_battle_v001_card_plan(
                noble_indices=noble_indices,
                card_owners=card_owners,
                servant_priority=servant_priority,
                cards=cards,
                support_attacker=support_attacker,
            )
        else:
            plan = build_command_card_plan(
                noble_indices=noble_indices,
                card_owners=card_owners,
                servant_priority=servant_priority,
                cards=cards,
                support_attacker=support_attacker,
            )
        log.info("本回合出卡计划：%s", plan)
        return plan[:3]

    def _build_smart_battle_v001_card_plan(
        self,
        *,
        noble_indices: list[int],
        card_owners: dict[int, str | None],
        servant_priority: list[str],
        cards: list[CommandCardInfo] | None,
        support_attacker: str | None,
    ) -> list[dict[str, int]]:
        ordered_nobles = self._order_main_nobles(
            noble_indices,
            servant_priority=servant_priority,
            support_attacker=support_attacker,
        )
        plan: list[dict[str, int]] = [
            {"type": "noble", "index": servant_index}
            for servant_index in ordered_nobles[:3]
        ]
        if len(plan) >= 3:
            return plan[:3]

        used_cards: set[int] = set()
        support_cards = self._support_attacker_cards(
            cards=cards,
            card_owners=card_owners,
            support_attacker=support_attacker,
        )
        for card in support_cards:
            if len(plan) >= 3:
                return plan[:3]
            plan.append({"type": "card", "index": card.index})
            used_cards.add(card.index)

        if cards:
            remaining_cards = [
                CommandCardInfo(index=card.index, owner=card.owner, color=card.color)
                for card in sorted(cards, key=lambda item: item.index)
                if card.index not in used_cards
            ]
            for card in choose_best_card_chain(
                cards=remaining_cards,
                servant_priority=[],
                support_attacker=None,
            ):
                if len(plan) >= 3:
                    return plan[:3]
                if card.index in used_cards:
                    continue
                plan.append({"type": "card", "index": card.index})
                used_cards.add(card.index)

        for fallback in build_command_card_plan(
            noble_indices=[],
            card_owners=card_owners,
            servant_priority=servant_priority,
            cards=None,
            support_attacker=None,
        ):
            if len(plan) >= 3:
                break
            card_index = fallback["index"]
            if card_index in used_cards:
                continue
            plan.append({"type": "card", "index": card_index})
            used_cards.add(card_index)
        return plan[:3]

    def _build_custom_sequence_card_plan(
        self,
        np_statuses: list[ServantNpStatus],
    ) -> list[dict[str, int]]:
        active_plan = self.session.active_custom_turn_plan
        nobles = active_plan.nobles if active_plan is not None else []
        effective_nobles = self._merge_custom_nobles(
            getattr(self.session, "pending_custom_nobles", []),
            nobles,
        )
        np_status_by_index = {
            status.servant_index: status for status in np_statuses
        }
        ready_nobles: list[int] = []
        deferred_nobles: list[int] = []
        for noble_index in effective_nobles:
            status = np_status_by_index.get(noble_index)
            if status is not None and status.success and status.is_ready:
                ready_nobles.append(noble_index)
                continue
            deferred_nobles.append(noble_index)
        self.session.pending_custom_nobles = deferred_nobles

        cards, prediction = self._read_command_cards()
        support_attacker: str | None = None
        if cards is None:
            cards = self._read_custom_color_cards()
        elif prediction is not None and prediction.has_low_confidence:
            log.warning("自定义操作序列普通卡归属低置信度，已回退为仅按颜色出卡")
            cards = [
                CommandCardInfo(index=card.index, owner=None, color=card.color)
                for card in cards
            ]
        else:
            support_attacker = self.session.support_attacker_servant_name()
        for card in cards:
            if not card.color:
                raise RuntimeError(
                    f"自定义操作序列普通卡颜色识别失败，卡位 {card.index} 无法确认颜色。"
                )
        plan = self._build_custom_sequence_attack_plan(
            noble_indices=ready_nobles,
            cards=cards,
            support_attacker=support_attacker,
        )
        log.info(
            "自定义操作序列本回合出卡计划：wave_turn=%s ready_nobles=%s deferred_nobles=%s plan=%s",
            self._custom_turn_key(active_plan),
            ready_nobles,
            deferred_nobles,
            plan,
        )
        return plan[:3]

    def _build_custom_sequence_attack_plan(
        self,
        *,
        noble_indices: list[int],
        cards: list[CommandCardInfo],
        support_attacker: str | None,
    ) -> list[dict[str, int]]:
        plan: list[dict[str, int]] = [
            {"type": "noble", "index": servant_index} for servant_index in noble_indices[:3]
        ]
        if len(plan) >= 3:
            return plan[:3]

        sorted_cards = sorted(cards, key=lambda item: item.index)
        used_cards: set[int] = set()
        normalized_support_attacker = self._normalize_servant_name(support_attacker)
        if normalized_support_attacker:
            for card in sorted_cards:
                if len(plan) >= 3:
                    return plan[:3]
                if self._normalize_servant_name(card.owner) != normalized_support_attacker:
                    continue
                plan.append({"type": "card", "index": card.index})
                used_cards.add(card.index)

        remaining_cards = [
            CommandCardInfo(index=card.index, owner=None, color=card.color)
            for card in sorted_cards
            if card.index not in used_cards
        ]
        if remaining_cards:
            for card in choose_best_card_chain(
                cards=remaining_cards,
                servant_priority=[],
                support_attacker=None,
            ):
                if len(plan) >= 3:
                    return plan[:3]
                if card.index in used_cards:
                    continue
                plan.append({"type": "card", "index": card.index})
                used_cards.add(card.index)

        for card in sorted_cards:
            if len(plan) >= 3:
                break
            if card.index in used_cards:
                continue
            plan.append({"type": "card", "index": card.index})
            used_cards.add(card.index)
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
        self.waiter.wait_seconds("已完成出卡，等待战斗动画开始", 1.0)
        log.info("战斗动画处理中，等待重新出现战斗菜单或结算页")
        post_card_state = self.waiter.wait_post_card_battle_end(
            timeout=35.0,
            poll_interval=0.25,
            stable_hits=2,
        )
        if post_card_state == GameState.BATTLE_READY:
            log.info("战斗动画结束，专用等待已命中 BATTLE_READY")
            return
        if post_card_state == GameState.BATTLE_RESULT:
            log.info("战斗动画结束，专用等待已命中 BATTLE_RESULT")
            return

        log.warning("出卡后专用等待超时，已回退旧逻辑继续兜底")
        detection = self.waiter.wait_state_exit(
            {GameState.CARD_SELECT, GameState.UNKNOWN},
            timeout=5.0,
            poll_interval=0.5,
        )
        if detection is not None:
            log.info("战斗动画结束，兜底等待已切换到 %s", detection.state.name)
            return
        raise RuntimeError("战斗动画等待超时，已停止运行。")

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

    def _read_custom_color_cards(self) -> list[CommandCardInfo]:
        screen_rgb = self.session.get_latest_screen_rgb()
        cards: list[CommandCardInfo] = []
        for card_index, (x1, y1, x2, y2) in GameCoordinates.COMMAND_CARD_REGIONS.items():
            card_rgb = screen_rgb[y1:y2, x1:x2].copy()
            color = detect_command_card_color(card_rgb)
            if color is None:
                raise RuntimeError(
                    f"自定义操作序列普通卡颜色识别失败，卡位 {card_index} 无法确认颜色。"
                )
            cards.append(CommandCardInfo(index=card_index, owner=None, color=color))
        log.info(
            "自定义操作序列普通卡颜色：%s",
            [{"index": card.index, "color": card.color} for card in cards],
        )
        return cards

    @staticmethod
    def _merge_custom_nobles(
        pending_nobles: list[int],
        current_nobles: list[int],
    ) -> list[int]:
        merged: list[int] = []
        seen: set[int] = set()
        for noble_index in [*pending_nobles, *current_nobles]:
            if noble_index in seen:
                continue
            merged.append(noble_index)
            seen.add(noble_index)
        return merged

    @staticmethod
    def _normalize_servant_name(value: str | None) -> str:
        return str(value or "").replace("\\", "/").strip().strip("/")

    def _order_main_nobles(
        self,
        noble_indices: list[int],
        *,
        servant_priority: list[str],
        support_attacker: str | None,
    ) -> list[int]:
        normalized_priority = [
            self._normalize_servant_name(item)
            for item in servant_priority
            if self._normalize_servant_name(item)
        ]
        normalized_support = self._normalize_servant_name(support_attacker)
        priority_order: list[str] = []
        if normalized_support:
            priority_order.append(normalized_support)
        for item in normalized_priority:
            if item not in priority_order:
                priority_order.append(item)

        slot_to_servant = {
            index + 1: self._normalize_servant_name(servant_name)
            for index, servant_name in enumerate(self.session.frontline_servant_names())
        }

        def _rank(slot_index: int) -> tuple[int, int]:
            servant_name = slot_to_servant.get(slot_index, "")
            try:
                priority_rank = priority_order.index(servant_name)
            except ValueError:
                priority_rank = len(priority_order) + 10
            return (priority_rank, slot_index)

        return sorted(noble_indices, key=_rank)

    def _support_attacker_cards(
        self,
        *,
        cards: list[CommandCardInfo] | None,
        card_owners: dict[int, str | None],
        support_attacker: str | None,
    ) -> list[CommandCardInfo]:
        normalized_support = self._normalize_servant_name(support_attacker)
        if not normalized_support:
            return []
        if cards:
            return [
                card
                for card in sorted(cards, key=lambda item: item.index)
                if self._normalize_servant_name(card.owner) == normalized_support
            ]
        return [
            CommandCardInfo(index=index, owner=owner, color=None)
            for index, owner in sorted(card_owners.items())
            if self._normalize_servant_name(owner) == normalized_support
        ]

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
            image_path = masked_path = json_path = None
            if self.session.should_save_command_card_evidence(prediction):
                image_path, masked_path, json_path = (
                    self.session.save_command_card_evidence(
                        prediction,
                        screen_rgb,
                    )
                )
            cards = prediction.cards
        except Exception as exc:
            log.warning("普通指令卡识别失败，已回退默认出卡：%s", exc)
            return None, None
        if image_path is not None:
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

    @staticmethod
    def _custom_turn_key(plan: CustomTurnPlan | None) -> tuple[int, int] | None:
        if plan is None:
            return None
        wave = getattr(plan, "wave", None)
        turn = getattr(plan, "turn", None)
        if wave is None or turn is None:
            return None
        return (wave, turn)
