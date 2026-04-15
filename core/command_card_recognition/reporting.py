"""普通指令卡识别结果输出。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.command_card_recognition.layout import apply_local_masks, crop_absolute_region
from core.command_card_recognition.models import CommandCardPrediction
from core.support_recognition import write_png


def prediction_to_dict(
    prediction: CommandCardPrediction,
    *,
    context: dict[str, Any] | None = None,
    masked_preview_path: str | None = None,
    parts_preview_path: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "frontline_servants": list(prediction.frontline_servants),
        "support_attacker": prediction.support_attacker,
        "min_score": prediction.min_score,
        "min_margin": prediction.min_margin,
        "has_low_confidence": prediction.has_low_confidence,
        "joint_score": prediction.joint_score,
        "joint_margin": prediction.joint_margin,
        "joint_low_confidence": prediction.joint_low_confidence,
        "final_owners_by_index": prediction.owners,
        "assignment_candidates": [
            {
                "owners_by_index": candidate.owners_by_index,
                "score": candidate.score,
                "margin_from_best": candidate.margin_from_best,
            }
            for candidate in prediction.assignment_candidates
        ],
        "cards": [],
    }
    if context:
        data["context"] = context
    if masked_preview_path:
        data["masked_preview_path"] = masked_preview_path
    if parts_preview_path:
        data["parts_preview_path"] = parts_preview_path
    for trace in prediction.traces:
        data["cards"].append(
            {
                "index": trace.index,
                "owner": trace.owner,
                "color": trace.color,
                "score": trace.score,
                "margin": trace.margin,
                "support_badge": trace.support_badge,
                "low_confidence": trace.low_confidence,
                "scores": [
                    {
                        "servant_name": score.servant_name,
                        "score": score.score,
                        "route1_score": score.route1_score,
                        "route2_score": score.route2_score,
                        "valid_part_count": score.valid_part_count,
                        "visible_weight_sum": score.visible_weight_sum,
                        "part_scores": [
                            {
                                "part_name": part.part_name,
                                "score": part.score,
                                "route1_score": part.route1_score,
                                "route2_score": part.route2_score,
                                "gray_score": part.gray_score,
                                "edge_score": part.edge_score,
                                "visible_ratio": part.visible_ratio,
                                "texture_score": part.texture_score,
                                "weight": part.weight,
                                "bbox_local": part.bbox_local,
                                "bbox_abs": part.bbox_abs,
                            }
                            for part in score.part_scores
                        ],
                    }
                    for score in trace.scores
                ],
                "crop_region_abs": trace.crop_region_abs,
                "mask_rects_abs": trace.mask_rects_abs,
            }
        )
    return data


def format_prediction(prediction: CommandCardPrediction) -> str:
    lines = [
        "普通指令卡识别分析",
        f"frontline={prediction.frontline_servants}",
        f"support_attacker={prediction.support_attacker}",
        f"has_low_confidence={prediction.has_low_confidence}",
        f"joint_score={prediction.joint_score:.4f}",
        f"joint_margin={prediction.joint_margin:.4f}",
        f"joint_low_confidence={prediction.joint_low_confidence}",
    ]
    if prediction.assignment_candidates:
        lines.append(
            "joint_candidates="
            + ", ".join(
                (
                    f"{candidate.owners_by_index}"
                    f"@{candidate.score:.4f}"
                    f"(delta={candidate.margin_from_best:.4f})"
                )
                for candidate in prediction.assignment_candidates
            )
        )
    for trace in prediction.traces:
        score_text = ", ".join(
            (
                f"{item.servant_name}={item.score:.4f}"
                f"(r1={item.route1_score:.4f},r2={item.route2_score:.4f},parts={item.valid_part_count})"
            )
            for item in trace.scores
        )
        lines.append(
            (
                f"card#{trace.index} owner={trace.owner} color={trace.color} "
                f"score={trace.score:.4f} margin={trace.margin:.4f} "
                f"support_badge={trace.support_badge} low_confidence={trace.low_confidence} "
                f"scores=[{score_text}]"
            )
        )
    return "\n".join(lines)


def write_prediction_json(
    path: str | Path,
    prediction: CommandCardPrediction,
    *,
    context: dict[str, Any] | None = None,
    masked_preview_path: str | None = None,
    parts_preview_path: str | None = None,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            prediction_to_dict(
                prediction,
                context=context,
                masked_preview_path=masked_preview_path,
                parts_preview_path=parts_preview_path,
            ),
            file,
            ensure_ascii=False,
            indent=2,
        )
    return output_path


def write_masked_preview_image(
    path: str | Path,
    prediction: CommandCardPrediction,
    screen_rgb: np.ndarray,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    card_views: list[np.ndarray] = []
    for trace in prediction.traces:
        if trace.crop_region_abs is None:
            continue
        cropped = crop_absolute_region(screen_rgb, trace.crop_region_abs)
        if trace.mask_rects_abs:
            x1, y1, _, _ = trace.crop_region_abs
            local_masks = tuple(
                (left - x1, top - y1, right - x1, bottom - y1)
                for left, top, right, bottom in trace.mask_rects_abs
            )
            cropped = apply_local_masks(cropped, local_masks)
        label_height = 26
        preview = np.full(
            (cropped.shape[0] + label_height, cropped.shape[1], 3),
            20,
            dtype=np.uint8,
        )
        preview[label_height:, :, :] = cropped
        cv2.putText(
            preview,
            f"#{trace.index}",
            (8, 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (230, 230, 230),
            1,
            cv2.LINE_AA,
        )
        card_views.append(preview)
    if not card_views:
        raise ValueError("prediction does not contain masked card views")
    gap = 8
    height = max(view.shape[0] for view in card_views)
    width = sum(view.shape[1] for view in card_views) + gap * (len(card_views) - 1)
    canvas = np.full((height, width, 3), 15, dtype=np.uint8)
    cursor = 0
    for view in card_views:
        canvas[: view.shape[0], cursor : cursor + view.shape[1]] = view
        cursor += view.shape[1] + gap
    write_png(output_path, canvas)
    return output_path


def write_part_preview_image(
    path: str | Path,
    prediction: CommandCardPrediction,
    screen_rgb: np.ndarray,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    row_views: list[np.ndarray] = []
    for trace in prediction.traces:
        part_scores = _best_part_scores(trace)
        if trace.crop_region_abs is None or not part_scores:
            continue
        cropped = crop_absolute_region(screen_rgb, trace.crop_region_abs)
        if trace.mask_rects_abs:
            x1, y1, _, _ = trace.crop_region_abs
            local_masks = tuple(
                (left - x1, top - y1, right - x1, bottom - y1)
                for left, top, right, bottom in trace.mask_rects_abs
            )
            cropped = apply_local_masks(cropped, local_masks)

        patch_views: list[np.ndarray] = []
        for part in part_scores:
            if part.bbox_local is None:
                continue
            x1, y1, x2, y2 = part.bbox_local
            patch = cropped[y1:y2, x1:x2].copy()
            if patch.size == 0:
                continue
            patch = cv2.resize(patch, (120, 120), interpolation=cv2.INTER_AREA)
            label_height = 34
            preview = np.full((120 + label_height, 120, 3), 18, dtype=np.uint8)
            preview[label_height:, :, :] = patch
            cv2.putText(
                preview,
                part.part_name,
                (6, 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (230, 230, 230),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                preview,
                f"{part.score:.3f}/{part.visible_ratio:.2f}",
                (6, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (180, 220, 255),
                1,
                cv2.LINE_AA,
            )
            patch_views.append(preview)

        if not patch_views:
            continue
        gap = 6
        width = sum(view.shape[1] for view in patch_views) + gap * (len(patch_views) - 1)
        height = max(view.shape[0] for view in patch_views) + 28
        row = np.full((height, width, 3), 12, dtype=np.uint8)
        cv2.putText(
            row,
            f"card#{trace.index} owner={trace.owner} color={trace.color}",
            (8, 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )
        cursor = 0
        for view in patch_views:
            row[28 : 28 + view.shape[0], cursor : cursor + view.shape[1]] = view
            cursor += view.shape[1] + gap
        row_views.append(row)

    if not row_views:
        raise ValueError("prediction does not contain part previews")

    gap = 8
    width = max(view.shape[1] for view in row_views)
    height = sum(view.shape[0] for view in row_views) + gap * (len(row_views) - 1)
    canvas = np.full((height, width, 3), 10, dtype=np.uint8)
    cursor = 0
    for view in row_views:
        canvas[cursor : cursor + view.shape[0], : view.shape[1]] = view
        cursor += view.shape[0] + gap
    write_png(output_path, canvas)
    return output_path


def _best_part_scores(trace) -> list[Any]:
    if not trace.scores:
        return []
    return trace.scores[0].part_scores
