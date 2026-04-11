"""长时间等待助战命中，只做识别与留证，不执行点击。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.device.adb_controller import AdbController
from core.shared import BattleConfig, GameCoordinates, GameState, load_battle_config
from core.perception import ImageRecognizer, StateDetectionResult, StateDetector
from core.shared.resource_catalog import ResourceCatalog
from core.support_recognition import write_png
from core.support_recognition.verifier import (
    SupportPortraitVerification,
    SupportPortraitVerifier,
)

log = logging.getLogger("scripts.watch_support_match")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="持续下滑助战列表，命中后留证退出")
    parser.add_argument("--servant", help="临时覆盖目标从者 slug")
    parser.add_argument("--output-dir", help="命中证据输出目录")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="不在助战页时的检测间隔（秒）",
    )
    parser.add_argument(
        "--swipe-delay",
        type=float,
        default=3.0,
        help="每次下滑后的等待时间（秒）",
    )
    return parser.parse_args()


def setup_logging(config: BattleConfig) -> None:
    level_name = config.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    if level_name not in logging.getLevelNamesMapping():
        log.warning("未知日志级别 %s，已回退到 INFO", config.log_level)


def resolve_output_dir(
    resources: ResourceCatalog,
    servant_name: str,
    raw_output_dir: str | None,
) -> Path:
    if raw_output_dir:
        return Path(raw_output_dir)
    return Path(resources.assets_dir) / "screenshots" / "support_watch" / servant_name


class SupportMatchWatcher:
    """持续等待助战页并滑动搜索目标从者，命中后留证退出。"""

    def __init__(
        self,
        *,
        adb: AdbController,
        recognizer: ImageRecognizer,
        verifier: SupportPortraitVerifier,
        resources: ResourceCatalog,
        servant_name: str,
        output_dir: Path,
        poll_interval: float,
        swipe_delay: float,
    ) -> None:
        self.adb = adb
        self.recognizer = recognizer
        self.verifier = verifier
        self.resources = resources
        self.servant_name = servant_name
        self.output_dir = output_dir
        self.poll_interval = poll_interval
        self.swipe_delay = swipe_delay
        self._latest_screen_image: Optional[np.ndarray] = None
        self._latest_screen_rgb: Optional[np.ndarray] = None
        self._last_state: Optional[GameState] = None
        self._swipe_count = 0
        self._miss_count = 0
        self.state_detector = StateDetector(
            recognizer=recognizer,
            screen_callback=self._refresh_screen,
            resources=resources,
            screen_array_callback=self._get_latest_screen_image,
        )

    def run(self) -> int:
        try:
            while True:
                detection = self.state_detector.detect()
                self._log_state_change(detection)

                if detection.state != GameState.SUPPORT_SELECT:
                    time.sleep(self.poll_interval)
                    continue

                initial_screen = self._get_latest_screen_rgb()
                if self._run_round(initial_screen):
                    return 0
                self._scroll_support_list()
        except KeyboardInterrupt:
            log.warning("收到手动中断，脚本退出")
            return 130

    def _run_round(self, initial_screen: np.ndarray) -> bool:
        initial_analysis = self.verifier.analyze(initial_screen)
        if not self.verifier.is_confident(initial_analysis):
            miss_paths = self._save_non_hit_artifacts(
                screen_rgb=initial_screen,
                analysis=initial_analysis,
                reason="initial_low",
            )
            self._log_non_match(initial_analysis, miss_paths=miss_paths)
            return False

        time.sleep(self.verifier.config.confirm_delay)
        self._refresh_screen()
        confirm_screen = self._get_latest_screen_rgb()
        match_result = self.verifier.confirm_match(initial_screen, confirm_screen)
        if match_result is None:
            confirm_analysis = self.verifier.analyze(confirm_screen)
            miss_paths = self._save_non_hit_artifacts(
                screen_rgb=confirm_screen,
                analysis=confirm_analysis,
                reason="confirm_reject",
            )
            self._log_non_match(confirm_analysis, miss_paths=miss_paths)
            return False

        final_analysis = self.verifier.analyze(confirm_screen)
        hit_paths = self._save_hit_artifacts(
            screen_rgb=confirm_screen,
            analysis=final_analysis,
            match_result=match_result,
        )
        log.info(
            "命中目标助战 servant=%s slot=%s score=%.3f confirm=%.3f margin=%.3f files=%s",
            self.servant_name,
            match_result.slot_index,
            match_result.score,
            match_result.confirm_score,
            match_result.margin,
            hit_paths,
        )
        return True

    def _refresh_screen(self) -> str:
        image = self.adb.screenshot_array(self.resources.screen_path)
        self._latest_screen_rgb = np.array(image)
        self._latest_screen_image = cv2.cvtColor(
            self._latest_screen_rgb,
            cv2.COLOR_RGB2GRAY,
        )
        return self.resources.screen_path

    def _get_latest_screen_image(self) -> np.ndarray:
        if self._latest_screen_image is None:
            self._refresh_screen()
        return self._latest_screen_image

    def _get_latest_screen_rgb(self) -> np.ndarray:
        if self._latest_screen_rgb is None:
            self._refresh_screen()
        return self._latest_screen_rgb

    def _log_state_change(self, detection: StateDetectionResult) -> None:
        if detection.state == self._last_state:
            return
        self._last_state = detection.state
        if detection.state == GameState.SUPPORT_SELECT:
            log.info("检测到助战选择界面，开始持续识别 %s", self.servant_name)
            return
        if detection.best_match_state is not None:
            log.info(
                "当前不在助战页 state=%s best=%s score=%.2f，继续等待",
                detection.state.name,
                detection.best_match_state.name,
                detection.best_score,
            )
            return
        log.info("当前不在助战页 state=%s，继续等待", detection.state.name)

    def _log_non_match(
        self,
        analysis: SupportPortraitVerification,
        *,
        miss_paths: Optional[dict[str, str]] = None,
    ) -> None:
        best_slot = analysis.best_slot
        if best_slot is None:
            log.info(
                "当前页未得到有效候选，准备下滑 swipe=%s files=%s",
                self._swipe_count,
                miss_paths,
            )
            return
        log.info(
            "当前页未命中 servant=%s best_slot=%s best_score=%.3f margin=%.3f swipe=%s files=%s",
            self.servant_name,
            best_slot.slot_index,
            best_slot.score,
            analysis.margin,
            self._swipe_count,
            miss_paths,
        )

    def _scroll_support_list(self) -> None:
        self.adb.swipe(
            GameCoordinates.SUPPORT_SCROLL_START[0],
            GameCoordinates.SUPPORT_SCROLL_START[1],
            GameCoordinates.SUPPORT_SCROLL_END[0],
            GameCoordinates.SUPPORT_SCROLL_END[1],
            duration=0.2,
        )
        self._swipe_count += 1
        log.info("已执行一次助战列表下滑 swipe=%s", self._swipe_count)
        time.sleep(self.swipe_delay)

    def _save_hit_artifacts(
        self,
        *,
        screen_rgb: np.ndarray,
        analysis: SupportPortraitVerification,
        match_result,
    ) -> dict[str, str]:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = self.output_dir / f"hit_{timestamp}.png"
        annotated_path = self.output_dir / f"hit_{timestamp}_annotated.png"
        summary_path = self.output_dir / f"hit_{timestamp}.json"

        write_png(screenshot_path, screen_rgb)
        write_png(annotated_path, self.verifier.build_annotated_image(screen_rgb, analysis))
        payload = {
            "timestamp": timestamp,
            "servant": self.servant_name,
            "backend": "embedding",
            "slot_index": match_result.slot_index,
            "score": match_result.score,
            "confirm_score": match_result.confirm_score,
            "margin": match_result.margin,
            "click_position": list(match_result.click_position),
            "best_positive_name": match_result.best_positive_name,
            "best_negative_name": match_result.best_negative_name,
            "swipe_count": self._swipe_count,
            "analysis": {
                "best_slot": None if analysis.best_slot is None else analysis.best_slot.slot_index,
                "second_slot": None if analysis.second_slot is None else analysis.second_slot.slot_index,
                "margin": analysis.margin,
                "min_score": analysis.min_score,
                "min_margin": analysis.min_margin,
                "slot_scores": [
                    {
                        "slot_index": item.slot_index,
                        "score": item.score,
                        "positive_score": item.positive_score,
                        "negative_score": item.negative_score,
                        "square_positive": item.square_positive,
                        "face_positive": item.face_positive,
                        "square_negative": item.square_negative,
                        "face_negative": item.face_negative,
                        "best_positive_name": item.best_positive_name,
                        "best_negative_name": item.best_negative_name,
                        "region": list(item.region),
                        "click_position": list(item.click_position),
                    }
                    for item in analysis.slot_scores
                ],
            },
        }
        summary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "screenshot": str(screenshot_path),
            "annotated": str(annotated_path),
            "summary": str(summary_path),
        }

    def _save_non_hit_artifacts(
        self,
        *,
        screen_rgb: np.ndarray,
        analysis: SupportPortraitVerification,
        reason: str,
    ) -> dict[str, str]:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._miss_count += 1
        miss_tag = f"miss_{self._miss_count:04d}_{reason}_{timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = self.output_dir / f"{miss_tag}.png"
        annotated_path = self.output_dir / f"{miss_tag}_annotated.png"
        summary_path = self.output_dir / f"{miss_tag}.json"

        write_png(screenshot_path, screen_rgb)
        write_png(annotated_path, self.verifier.build_annotated_image(screen_rgb, analysis))
        payload = {
            "timestamp": timestamp,
            "servant": self.servant_name,
            "backend": "embedding",
            "result": "miss",
            "reason": reason,
            "swipe_count": self._swipe_count,
            "miss_count": self._miss_count,
            "analysis": {
                "best_slot": None if analysis.best_slot is None else analysis.best_slot.slot_index,
                "second_slot": None if analysis.second_slot is None else analysis.second_slot.slot_index,
                "margin": analysis.margin,
                "min_score": analysis.min_score,
                "min_margin": analysis.min_margin,
                "slot_scores": [
                    {
                        "slot_index": item.slot_index,
                        "score": item.score,
                        "positive_score": item.positive_score,
                        "negative_score": item.negative_score,
                        "square_positive": item.square_positive,
                        "face_positive": item.face_positive,
                        "square_negative": item.square_negative,
                        "face_negative": item.face_negative,
                        "best_positive_name": item.best_positive_name,
                        "best_negative_name": item.best_negative_name,
                        "region": list(item.region),
                        "click_position": list(item.click_position),
                    }
                    for item in analysis.slot_scores
                ],
            },
        }
        summary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "screenshot": str(screenshot_path),
            "annotated": str(annotated_path),
            "summary": str(summary_path),
        }


def main() -> int:
    args = parse_args()
    config = load_battle_config(str(REPO_ROOT / "config" / "battle_config.yaml"))
    setup_logging(config)

    servant_name = (args.servant or config.support.servant).strip()
    if not servant_name:
        raise SystemExit("未提供目标从者，请在 battle_config.yaml 或 --servant 中设置")

    resources = ResourceCatalog(str(REPO_ROOT / "assets"))
    recognizer = ImageRecognizer(threshold=config.match_threshold)
    adb = AdbController()
    verifier = SupportPortraitVerifier.from_servant(
        servant_name=servant_name,
        resources=resources,
        config=config.support.recognition,
    )
    watcher = SupportMatchWatcher(
        adb=adb,
        recognizer=recognizer,
        verifier=verifier,
        resources=resources,
        servant_name=servant_name,
        output_dir=resolve_output_dir(resources, servant_name, args.output_dir),
        poll_interval=args.poll_interval,
        swipe_delay=args.swipe_delay,
    )
    return watcher.run()


if __name__ == "__main__":
    raise SystemExit(main())
