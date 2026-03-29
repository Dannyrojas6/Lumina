"""战斗快照识别层，集中产出智能战斗 v1 需要的最小信息。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional

import cv2
import numpy as np

from core.battle_ocr import BattleOcrReader, ServantNpStatus
from core.coordinates import GameCoordinates

log = logging.getLogger("core.battle_snapshot")

BASE_SCREEN_SIZE = (1920, 1080)


@dataclass(frozen=True)
class SkillAvailability:
    """描述单个技能位是否可点击。"""

    slot_index: int
    available: bool
    score: float
    reason: str


@dataclass(frozen=True)
class BattleSnapshot:
    """战斗识别结果的最小骨架。"""

    wave_index: Optional[int]
    enemy_count: Optional[int]
    current_turn: Optional[int]
    frontline_np: list[ServantNpStatus]
    skill_availability: dict[int, SkillAvailability]


class BattleSnapshotReader:
    """把战斗画面拆成波次、敌人数、前排 NP 和技能可用性。"""

    def __init__(
        self,
        battle_ocr: Optional[BattleOcrReader] = None,
        *,
        wave_banner_template_path: Optional[str] = None,
        wave_match_threshold: float = 0.6,
        skill_available_threshold: float = 0.54,
        skill_uncertain_threshold: float = 0.48,
        debug_dir: Optional[str] = None,
    ) -> None:
        self.battle_ocr = battle_ocr or BattleOcrReader(debug_dir=debug_dir)
        self.wave_match_threshold = wave_match_threshold
        self.skill_available_threshold = skill_available_threshold
        self.skill_uncertain_threshold = skill_uncertain_threshold

    def read_snapshot(self, screen: np.ndarray) -> BattleSnapshot:
        """从当前战斗画面生成快照。"""
        normalized = self._normalize_screen(screen)
        frontline_np = self.battle_ocr.read_np_statuses(normalized)
        wave_index = self._read_wave_index(normalized)
        enemy_count = self._read_enemy_count(normalized)
        current_turn = self._read_current_turn(normalized)
        skill_availability = self._read_skill_availability(normalized)
        return BattleSnapshot(
            wave_index=wave_index,
            enemy_count=enemy_count,
            current_turn=current_turn,
            frontline_np=frontline_np,
            skill_availability=skill_availability,
        )

    def read_snapshot_from_path(self, image_path: str | Path) -> BattleSnapshot:
        """从截图文件读取快照。"""
        raw_bytes = np.fromfile(str(image_path), dtype=np.uint8)
        if raw_bytes.size == 0:
            raise FileNotFoundError(f"无法读取截图：{image_path}")

        screen = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
        if screen is None:
            raise FileNotFoundError(f"无法读取截图：{image_path}")

        screen_rgb = cv2.cvtColor(self._normalize_screen(screen), cv2.COLOR_BGR2RGB)
        return self.read_snapshot(screen_rgb)

    def _read_wave_index(self, screen: np.ndarray) -> Optional[int]:
        crop = self._crop_region(screen, GameCoordinates.BATTLE_WAVE_CURRENT_REGION)
        text, confidence = self.battle_ocr.read_text(crop, label="battle_wave_current")
        wave_index = self._extract_single_count(text)
        log.debug(
            "wave 识别 confidence=%.2f text=%s wave_index=%s",
            confidence,
            text,
            wave_index,
        )
        return wave_index

    def _read_enemy_count(self, screen: np.ndarray) -> Optional[int]:
        crop = self._crop_region(screen, GameCoordinates.BATTLE_ENEMY_COUNT_REGION)
        text, confidence = self.battle_ocr.read_text(crop, label="battle_enemy")
        enemy_count = self._extract_single_count(text)
        log.debug(
            "enemy 识别 confidence=%.2f text=%s enemy_count=%s",
            confidence,
            text,
            enemy_count,
        )
        if enemy_count in (1, 2, 3):
            return enemy_count

        fallback_count = self._fallback_enemy_count(screen)
        log.debug("enemy 识别回退值=%s", fallback_count)
        return fallback_count

    def _read_current_turn(self, screen: np.ndarray) -> Optional[int]:
        crop = self._crop_region(screen, GameCoordinates.BATTLE_TURN_REGION)
        text, confidence = self.battle_ocr.read_text(crop, label="battle_turn")
        current_turn = self._extract_positive_number(text)
        log.debug(
            "turn 识别 confidence=%.2f text=%s current_turn=%s",
            confidence,
            text,
            current_turn,
        )
        return current_turn

    def _read_skill_availability(
        self,
        screen: np.ndarray,
    ) -> dict[int, SkillAvailability]:
        availability: dict[int, SkillAvailability] = {}
        for slot_index in GameCoordinates.BATTLE_SKILL_REGIONS:
            availability[slot_index] = self._read_single_skill_availability(
                screen,
                slot_index,
            )
        return availability

    def _read_single_skill_availability(
        self,
        screen: np.ndarray,
        slot_index: int,
    ) -> SkillAvailability:
        body_region = GameCoordinates.BATTLE_SKILL_BODY_REGIONS[slot_index]
        body_crop = self._crop_region(screen, body_region)
        body_score = self._skill_score(body_crop)

        if body_score >= self.skill_available_threshold:
            reason = "body_ready"
            available = True
            right_text = ""
            right_value = None
            right_success = False
            left_text = ""
            left_confidence = 0.0
        else:
            right_region = GameCoordinates.BATTLE_SKILL_RIGHT_CORNER_REGIONS[slot_index]
            right_crop = self._crop_region(screen, right_region)
            right_result = self.battle_ocr.read_skill_corner_number(
                right_crop,
                label=f"skill_{slot_index}_right",
            )
            right_text = right_result.text
            right_value = right_result.value
            right_success = right_result.success
            left_text = ""
            left_confidence = 0.0

            if right_success and right_value is not None and right_value > 0:
                reason = "cooldown_right"
                available = False
            else:
                left_region = GameCoordinates.BATTLE_SKILL_LEFT_CORNER_REGIONS[slot_index]
                left_crop = self._crop_region(screen, left_region)
                left_text, left_confidence = self.battle_ocr.read_skill_corner_text(
                    left_crop,
                    label=f"skill_{slot_index}_left",
                )
                if self._looks_like_skill_cooldown_hint(left_text):
                    reason = "cooldown_left"
                    available = False
                elif body_score >= self.skill_uncertain_threshold:
                    reason = "body_uncertain"
                    available = False
                else:
                    reason = "body_dark"
                    available = False

        log.debug(
            "skill 识别 slot=%s available=%s reason=%s body_score=%.3f right_text=%s "
            "right_value=%s right_success=%s left_text=%s left_confidence=%.2f",
            slot_index,
            available,
            reason,
            body_score,
            right_text,
            right_value,
            right_success,
            left_text,
            left_confidence,
        )
        return SkillAvailability(
            slot_index=slot_index,
            available=available,
            score=body_score,
            reason=reason,
        )

    def _fallback_enemy_count(self, screen: np.ndarray) -> Optional[int]:
        count = 0
        for region in GameCoordinates.BATTLE_ENEMY_FALLBACK_REGIONS.values():
            crop = self._crop_region(screen, region)
            if self._enemy_presence_score(crop) >= 0.24:
                count += 1
        if count in (1, 2, 3):
            return count
        return None

    def _enemy_presence_score(self, crop: np.ndarray) -> float:
        if crop.size == 0:
            return 0.0
        gray = self._to_gray(crop)
        hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
        value_score = float(np.mean(hsv[:, :, 2])) / 255.0
        color_score = float(np.mean(hsv[:, :, 1])) / 255.0
        edge_score = float(np.mean(cv2.Canny(gray, 60, 180) > 0))
        return (0.45 * value_score) + (0.35 * color_score) + (0.20 * edge_score)

    def _skill_score(self, crop: np.ndarray) -> float:
        if crop.size == 0:
            return 0.0
        gray = self._to_gray(crop)
        hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
        value_score = float(np.mean(hsv[:, :, 2])) / 255.0
        saturation_score = float(np.mean(hsv[:, :, 1])) / 255.0
        contrast_score = float(np.std(gray)) / 255.0
        return (0.45 * value_score) + (0.4 * saturation_score) + (0.15 * contrast_score)

    def _normalize_screen(self, screen: np.ndarray) -> np.ndarray:
        if screen.shape[1] != BASE_SCREEN_SIZE[0] or screen.shape[0] != BASE_SCREEN_SIZE[1]:
            screen = cv2.resize(screen, BASE_SCREEN_SIZE)
        return screen

    def _crop_region(
        self,
        screen: np.ndarray,
        region: tuple[int, int, int, int],
    ) -> np.ndarray:
        x1, y1, x2, y2 = region
        return screen[y1:y2, x1:x2]


    def _to_gray(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    def _extract_single_count(self, text: str) -> Optional[int]:
        digit_map = {"一": 1, "二": 2, "三": 3}
        for char in text:
            if char.isdigit():
                value = int(char)
                if value in (1, 2, 3):
                    return value
            if char in digit_map:
                return digit_map[char]
        return None

    def _extract_positive_number(self, text: str) -> Optional[int]:
        digits = re.findall(r"\d+", text)
        if not digits:
            return None
        value = int("".join(digits))
        return value if value > 0 else None

    def _looks_like_skill_cooldown_hint(self, text: str) -> bool:
        normalized = re.sub(r"\s+", "", text)
        if not normalized:
            return False
        if "剩" in normalized or "余" in normalized:
            return True
        return any(int(item) > 0 for item in re.findall(r"\d+", normalized))


