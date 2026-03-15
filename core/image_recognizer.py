import logging
from optparse import Option
from pathlib import Path
from typing import Optional

import cv2

log = logging.getLogger("core.image_recognizer")


class ImageRecognizer:
    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = threshold

    def match(
        self, template_path: str, screen_path: str, threshold: Optional[float] = None
    ) -> Optional[tuple[int, int]]:
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        screen = cv2.imread(screen_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            log.warning(f"template load error: {template_path}")
            return None
        if screen is None:
            log.warning(f"screenshot load error: {screen_path}")
            return None

        if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
            log.warning(
                f"the template size exceeds the screenshot! {Path(template_path).name}"
            )
            return None

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        thr = threshold if threshold is not None else self.threshold
        if max_val >= thr:
            h, w = template.shape
            cx, cy = max_loc[0] + w // 2, max_loc[1] + h // 2
            log.debug(
                f"match success [{max_val:.2f}] {Path(template_path).name} -> ({cx},{cy})"
            )
            return cx, cy

        log.debug(f"match failed! [{max_val:.2f}] {Path(template_path).name}")
        return None
