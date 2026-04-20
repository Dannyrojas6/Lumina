"""运行时会话状态与共享依赖。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from core.battle_runtime import (
    BattleAction,
    BattleSnapshotReader,
)
from core.command_card_recognition import (
    CommandCardPrediction,
    CommandCardRecognizer,
    write_masked_preview_image,
    write_part_preview_image,
    write_prediction_json,
)
from core.device import AdbController
from core.perception import BattleOcrReader, ImageRecognizer
from core.perception.battle_ocr import ServantNpStatus
from core.shared import BattleConfig, GameState, ResourceCatalog
from core.shared.config_models import CustomTurnPlan
from core.support_recognition.verifier import SupportPortraitVerifier

log = logging.getLogger("core.runtime.session")

UNKNOWN_SNAPSHOT_DAILY_LIMIT = 10
UNKNOWN_SNAPSHOT_TOTAL_LIMIT = 30
COMMAND_CARD_EVIDENCE_DAILY_LIMIT = 10
COMMAND_CARD_EVIDENCE_TOTAL_LIMIT = 30


@dataclass
class RuntimeSession:
    """集中保存运行时依赖与会话状态。"""

    adb: AdbController
    recognizer: ImageRecognizer
    battle: BattleAction
    config: BattleConfig
    resources: ResourceCatalog
    battle_ocr: Optional[BattleOcrReader] = None
    battle_snapshot_reader: Optional[BattleSnapshotReader] = None
    state: GameState = GameState.UNKNOWN
    latest_screen_image: Optional[np.ndarray] = None
    latest_screen_rgb: Optional[np.ndarray] = None
    loop_done: int = 0
    battle_actions_done: bool = False
    used_servant_skills: set[int] = field(default_factory=set)
    last_wave_index: Optional[int] = None
    last_enemy_count: Optional[int] = None
    last_current_turn: Optional[int] = None
    last_processed_turn: Optional[int] = None
    last_processed_custom_turn: tuple[int, int] | None = None
    active_custom_turn_plan: CustomTurnPlan | None = None
    pending_custom_nobles: list[int] = field(default_factory=list)
    stop_requested: bool = False
    unknown_snapshot_saved: bool = False
    consecutive_unknown_count: int = 0
    unknown_fallback_attempts_this_turn: int = 0
    unknown_last_fallback_template: str | None = None
    unknown_last_fallback_click_time: float | None = None
    ap_recovery_consecutive_hits: int = 0
    ap_recovery_window_started_at: float | None = None
    ap_recovery_last_hit_time: float | None = None
    support_verifiers: dict[str, SupportPortraitVerifier] = field(default_factory=dict)
    command_card_recognizer: Optional[CommandCardRecognizer] = None
    on_state_changed: Callable[[GameState], None] | None = None
    on_screen_rgb_updated: Callable[[np.ndarray], None] | None = None

    @property
    def smart_battle_enabled(self) -> bool:
        return bool(
            self.config.battle_mode == "main" and self.config.smart_battle.enabled
        )

    @property
    def custom_sequence_enabled(self) -> bool:
        return bool(
            self.config.battle_mode == "custom_sequence"
            and self.battle_snapshot_reader is not None
        )

    def refresh_screen(self) -> str:
        """更新当前截图文件并返回其路径。"""
        save_path = (
            self.resources.screen_path if self.config.save_debug_screenshots else None
        )
        image = self.adb.screenshot_array(save_path)
        self.latest_screen_rgb = np.array(image)
        self.latest_screen_image = cv2.cvtColor(
            self.latest_screen_rgb, cv2.COLOR_RGB2GRAY
        )
        if self.on_screen_rgb_updated is not None:
            self.on_screen_rgb_updated(np.array(self.latest_screen_rgb, copy=True))
        return self.resources.screen_path

    def get_latest_screen_image(self) -> np.ndarray:
        """返回最近一次刷新的灰度截图。"""
        if self.latest_screen_image is None:
            self.refresh_screen()
        return self.latest_screen_image

    def get_latest_screen_rgb(self) -> np.ndarray:
        """返回最近一次刷新的 RGB 截图。"""
        if self.latest_screen_rgb is None:
            self.refresh_screen()
        return self.latest_screen_rgb

    def save_unknown_snapshot(self) -> Optional[str]:
        """将当前未识别截图落盘，便于排查识别失败原因。"""
        if self.latest_screen_rgb is None:
            return None

        screenshot_root = Path(self.resources.screen_path).parent / "unknown"
        date_dir = screenshot_root / time.strftime("%Y%m%d")
        screenshot_dir = date_dir
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._prune_oldest_files(
            screenshot_dir,
            suffix=".png",
            keep_at_most=UNKNOWN_SNAPSHOT_DAILY_LIMIT - 1,
        )
        self._prune_oldest_files(
            screenshot_root,
            suffix=".png",
            keep_at_most=UNKNOWN_SNAPSHOT_TOTAL_LIMIT - 1,
        )
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_path = screenshot_dir / f"unknown_{timestamp}.png"
        if not cv2.imwrite(
            str(save_path), cv2.cvtColor(self.latest_screen_rgb, cv2.COLOR_RGB2BGR)
        ):
            log.warning("unknown 留证写盘失败 path=%s", save_path)
            return None
        return str(save_path)

    def get_support_verifier(
        self,
        servant_name: str,
    ) -> Optional[SupportPortraitVerifier]:
        """按需加载目标从者的人物头像核验器。"""
        if servant_name in self.support_verifiers:
            return self.support_verifiers[servant_name]
        try:
            verifier = SupportPortraitVerifier.from_servant(
                servant_name=servant_name,
                resources=self.resources,
                config=self.config.support.recognition,
            )
        except (FileNotFoundError, ValueError) as exc:
            log.warning("助战头像核验器未启用 servant=%s reason=%s", servant_name, exc)
            return None
        self.support_verifiers[servant_name] = verifier
        return verifier

    def get_command_card_recognizer(self) -> CommandCardRecognizer:
        """按需加载普通卡识别器。"""
        if self.command_card_recognizer is None:
            self.command_card_recognizer = CommandCardRecognizer(self.resources)
        return self.command_card_recognizer

    def save_command_card_evidence(
        self,
        prediction: CommandCardPrediction,
        screen_rgb: np.ndarray,
    ) -> tuple[str, str, str]:
        """保存本回合普通卡识别证据。"""
        evidence_root = Path(self.resources.command_card_debug_dir)
        evidence_dir = evidence_root / time.strftime("%Y%m%d")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        self._prune_oldest_command_card_groups(
            evidence_dir,
            keep_at_most=COMMAND_CARD_EVIDENCE_DAILY_LIMIT - 1,
        )
        self._prune_oldest_command_card_groups(
            evidence_root,
            keep_at_most=COMMAND_CARD_EVIDENCE_TOTAL_LIMIT - 1,
        )
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        milliseconds = int((time.time() % 1) * 1000)
        stem = f"command_cards_{timestamp}_{milliseconds:03d}"
        image_path = evidence_dir / f"{stem}.png"
        masked_path = evidence_dir / f"{stem}_masked.png"
        parts_path = evidence_dir / f"{stem}_parts.png"
        json_path = evidence_dir / f"{stem}.json"

        cv2.imwrite(str(image_path), cv2.cvtColor(screen_rgb, cv2.COLOR_RGB2BGR))
        write_masked_preview_image(masked_path, prediction, screen_rgb)
        write_part_preview_image(parts_path, prediction, screen_rgb)
        write_prediction_json(
            json_path,
            prediction,
            context={
                "current_turn": self.last_current_turn,
                "wave_index": self.last_wave_index,
                "loop_done": self.loop_done,
                "screen_path": str(image_path),
            },
            masked_preview_path=str(masked_path),
            parts_preview_path=str(parts_path),
        )
        return str(image_path), str(masked_path), str(json_path)

    @staticmethod
    def _count_files(root: Path, *, suffix: str) -> int:
        if not root.exists():
            return 0
        return sum(1 for path in root.rglob(f"*{suffix}") if path.is_file())

    def _prune_oldest_files(
        self,
        root: Path,
        *,
        suffix: str,
        keep_at_most: int,
    ) -> None:
        if keep_at_most < 0 or not root.exists():
            return
        files = sorted(
            (path for path in root.rglob(f"*{suffix}") if path.is_file()),
            key=lambda path: (path.stat().st_mtime, str(path)),
        )
        overflow = len(files) - keep_at_most
        if overflow <= 0:
            return
        for path in files[:overflow]:
            path.unlink(missing_ok=True)

    def _prune_oldest_command_card_groups(
        self,
        root: Path,
        *,
        keep_at_most: int,
    ) -> None:
        if keep_at_most < 0 or not root.exists():
            return
        json_files = sorted(
            (path for path in root.rglob("*.json") if path.is_file()),
            key=lambda path: (path.stat().st_mtime, str(path)),
        )
        overflow = len(json_files) - keep_at_most
        if overflow <= 0:
            return
        for json_path in json_files[:overflow]:
            stem = json_path.stem
            related_paths = (
                json_path.with_name(f"{stem}.png"),
                json_path.with_name(f"{stem}_masked.png"),
                json_path.with_name(f"{stem}_parts.png"),
                json_path,
            )
            for path in related_paths:
                path.unlink(missing_ok=True)

    def reset_unknown_runtime_state(self) -> None:
        self.unknown_snapshot_saved = False
        self.consecutive_unknown_count = 0
        self.unknown_fallback_attempts_this_turn = 0
        self.unknown_last_fallback_template = None
        self.unknown_last_fallback_click_time = None
        self.ap_recovery_consecutive_hits = 0
        self.ap_recovery_window_started_at = None
        self.ap_recovery_last_hit_time = None

    def should_save_command_card_evidence(
        self,
        prediction: CommandCardPrediction,
    ) -> bool:
        """判断当前回合是否需要落盘普通卡识别证据。"""
        return bool(self.config.save_debug_screenshots or prediction.has_low_confidence)

    def command_card_priority(self) -> list[str]:
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

    def frontline_servant_names(self) -> list[str]:
        """返回前排三人的完整从者标识。"""
        return [
            str(slot.servant).replace("\\", "/").strip().strip("/")
            for slot in self.config.smart_battle.frontline
            if str(slot.servant).strip()
        ]

    def support_attacker_servant_name(self) -> str | None:
        """返回助战打手的从者标识。"""
        for slot in self.config.smart_battle.frontline:
            if slot.is_support and slot.role == "attacker":
                return str(slot.servant).replace("\\", "/").strip().strip("/")
        return None

    def read_np_statuses(self) -> list[ServantNpStatus]:
        """从当前战斗截图中读取三位从者的 NP。"""
        if self.battle_ocr is None:
            raise RuntimeError("BattleOcrReader 未初始化，无法读取 NP。")

        statuses = self.battle_ocr.read_np_statuses(self.get_latest_screen_rgb())
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

    def mark_battle_result_complete(self) -> None:
        """在结算完成后重置本轮战斗状态。"""
        self.loop_done += 1
        self.battle_actions_done = False
        self.used_servant_skills.clear()
        self.last_wave_index = None
        self.last_enemy_count = None
        self.last_current_turn = None
        self.last_processed_turn = None
        self.last_processed_custom_turn = None
        self.active_custom_turn_plan = None
        self.pending_custom_nobles = []
