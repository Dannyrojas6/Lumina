from pathlib import Path
import os

import cv2
import numpy as np

from core.config import Config
from core.resources import ResourceCatalog
from core.support_portrait_recognition import SupportPortraitMatcher


def main() -> None:
    image_path = Path(os.environ['TARGET_IMAGE'])
    config = Config.load(Path('config/battle_config.yaml'))
    resources = ResourceCatalog()
    matcher = SupportPortraitMatcher.from_servant(
        'morgan',
        resources,
        config.support.recognition,
    )

    image = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    edge = cv2.Canny(gray, 48, 140)

    regions = {
        1: (74, 294, 317, 559),
        2: (74, 593, 320, 861),
        3: (70, 894, 322, 1063),
    }

    for idx, region in regions.items():
        x1, y1, x2, y2 = region
        window_gray = gray[y1:y2, x1:x2]
        window_edge = edge[y1:y2, x1:x2]
        score, components, template_path, variant_name = matcher._score_window(
            window_gray,
            window_edge,
        )
        rounded = {name: round(value, 4) for name, value in components.items()}
        print(
            idx,
            region,
            round(score, 4),
            rounded,
            Path(template_path).name if template_path else '',
            variant_name,
        )


if __name__ == '__main__':
    main()
