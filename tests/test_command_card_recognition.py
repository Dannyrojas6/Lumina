from pathlib import Path

import numpy as np

from core.command_card_recognition import (
    CommandCardRecognizer,
    collect_command_card_reference_paths,
    crop_command_card_face,
    mask_command_card_info_strip,
)
from core.coordinates import GameCoordinates
from core.resources import ResourceCatalog


def test_crop_command_card_face_uses_upper_half_only():
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    x1, y1, x2, y2 = GameCoordinates.COMMAND_CARD_REGIONS[1]
    midpoint = y1 + ((y2 - y1) // 2)
    screen[y1:midpoint, x1:x2] = 255
    screen[midpoint:y2, x1:x2] = [255, 0, 0]

    crop = crop_command_card_face(screen, GameCoordinates.COMMAND_CARD_REGIONS[1])

    assert crop.shape == (midpoint - y1, x2 - x1, 3)
    assert np.all(crop == 255)


def test_collect_command_card_reference_paths_reads_servant_commands():
    resources = ResourceCatalog()

    altria_paths = collect_command_card_reference_paths(
        resources, "caster/altria_caster"
    )
    morgan_paths = collect_command_card_reference_paths(resources, "berserker/morgan")

    assert len(altria_paths) == 3
    assert len(morgan_paths) == 4
    assert all(Path(path).suffix.lower() == ".png" for path in altria_paths)


def test_mask_command_card_info_strip_only_neutralizes_horizontal_band():
    crop = np.zeros((170, 270, 3), dtype=np.uint8)
    crop[:24, :] = 32
    crop[24:62, :] = 255
    crop[62:, :] = 96

    masked = mask_command_card_info_strip(crop)

    assert masked.shape == crop.shape
    assert np.all(masked[:24, :] == 32)
    assert np.all(masked[62:, :] == 96)
    assert not np.all(masked[24:62, :] == 255)


def test_recognize_frontline_matches_merlin_morgan_zhuge_sample():
    resources = ResourceCatalog()
    recognizer = CommandCardRecognizer(resources)
    screen = resources  # type: ignore[assignment]
    from core.portrait_embedding import load_rgb_image

    screen = load_rgb_image(
        r"D:\VSCodeRepository\Lumina\test_image\指令卡梅林摩根诸葛亮.png"
    )
    owners = recognizer.recognize_frontline(
        screen,
        [
            "caster/zhuge_liang",
            "caster/merlin",
            "berserker/morgan",
        ],
    )

    assert owners == {
        1: "berserker/morgan",
        2: "berserker/morgan",
        3: "caster/zhuge_liang",
        4: "caster/merlin",
        5: "caster/merlin",
    }
