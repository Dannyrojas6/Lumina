"""助战识别标注与调试辅助。"""

from __future__ import annotations

import cv2
import numpy as np

from core.shared.screen_coordinates import GameCoordinates


def annotate_support_screen(screen_rgb: np.ndarray, analysis) -> np.ndarray:
    annotated = cv2.cvtColor(screen_rgb, cv2.COLOR_RGB2BGR)
    strip_x1, strip_y1, strip_x2, strip_y2 = GameCoordinates.SUPPORT_PORTRAIT_STRIP
    cv2.rectangle(annotated, (strip_x1, strip_y1), (strip_x2, strip_y2), (255, 128, 0), 1)
    for item in analysis.slot_scores:
        color = (
            (0, 255, 0)
            if analysis.best_slot and item.slot_index == analysis.best_slot.slot_index
            else (0, 128, 255)
        )
        x1, y1, x2, y2 = GameCoordinates.SUPPORT_PORTRAIT_SLOT_REGIONS.get(
            item.slot_index,
            item.region,
        )
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            f"S{item.slot_index}:{item.score:.3f}",
            (x1 + 4, max(24, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )
    return cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
