"""普通指令卡识别模块。"""

from core.command_card_recognition.models import (
    CommandCardAssignmentCandidate,
    CommandCardInfo,
    CommandCardPartScore,
    CommandCardPrediction,
    CommandCardSample,
    CommandCardScore,
    CommandCardTrace,
)
from core.command_card_recognition.solver import (
    COMMAND_CARD_JOINT_MIN_MARGIN,
    HandAssignmentSolver,
)
from core.command_card_recognition.layout import (
    COMMAND_CARD_SLOT_LAYOUTS,
    COMMAND_CARD_PART_LAYOUTS,
    crop_command_card_for_recognition,
)
from core.command_card_recognition.cropper import (
    crop_command_card_face,
    detect_command_card_color,
)
from core.command_card_recognition.recognizer import (
    COMMAND_CARD_MIN_MARGIN,
    COMMAND_CARD_MIN_SCORE,
    CommandCardRecognizer,
    choose_best_card_chain,
    collect_command_card_reference_paths,
    mask_command_card_info_strip,
)
from core.command_card_recognition.metrics import compute_metrics
from core.command_card_recognition.reporting import (
    format_prediction,
    prediction_to_dict,
    write_masked_preview_image,
    write_part_preview_image,
    write_prediction_json,
)
from core.command_card_recognition.samples import load_command_card_samples

__all__ = [
    "COMMAND_CARD_MIN_MARGIN",
    "COMMAND_CARD_MIN_SCORE",
    "COMMAND_CARD_JOINT_MIN_MARGIN",
    "CommandCardAssignmentCandidate",
    "CommandCardInfo",
    "CommandCardPartScore",
    "CommandCardPrediction",
    "CommandCardRecognizer",
    "CommandCardSample",
    "CommandCardScore",
    "CommandCardTrace",
    "HandAssignmentSolver",
    "COMMAND_CARD_PART_LAYOUTS",
    "COMMAND_CARD_SLOT_LAYOUTS",
    "choose_best_card_chain",
    "compute_metrics",
    "collect_command_card_reference_paths",
    "crop_command_card_for_recognition",
    "crop_command_card_face",
    "detect_command_card_color",
    "format_prediction",
    "load_command_card_samples",
    "mask_command_card_info_strip",
    "prediction_to_dict",
    "write_masked_preview_image",
    "write_part_preview_image",
    "write_prediction_json",
]
