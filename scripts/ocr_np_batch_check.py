from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "test_image" / "ocr_np_samples.jsonl"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True)
class SampleCase:
    image: Path
    expected_np: tuple[int | None, int | None, int | None]
    note: str = ""


@dataclass(frozen=True)
class CaseResult:
    image: Path
    expected_np: tuple[int | None, int | None, int | None]
    actual_np: tuple[int, int, int] | None
    passed: bool
    message: str


@dataclass(frozen=True)
class BatchReport:
    total: int
    passed: int
    failed: int
    results: list[CaseResult]


def _resolve_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = REPO_ROOT / resolved
    return resolved


def load_sample_cases(manifest_path: str | Path) -> list[SampleCase]:
    manifest = _resolve_path(manifest_path)
    if not manifest.exists():
        raise FileNotFoundError(f"sample manifest not found: {manifest}")

    cases: list[SampleCase] = []
    for line_no, raw_line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        record = json.loads(raw_line)
        if "image" not in record or "expected_np" not in record:
            raise ValueError(f"invalid record at line {line_no}: {record!r}")

        image = _resolve_path(record["image"])
        expected_np_raw = record["expected_np"]
        if not isinstance(expected_np_raw, list) or len(expected_np_raw) != 3:
            raise ValueError(
                f"expected_np must be a 3-item list at line {line_no}: {record!r}"
            )

        expected_np = tuple(
            None if value is None else int(value) for value in expected_np_raw
        )
        note = str(record.get("note", ""))
        cases.append(SampleCase(image=image, expected_np=expected_np, note=note))

    return cases


def _normalize_np_values(values: Sequence[int]) -> tuple[int, int, int]:
    if len(values) != 3:
        raise ValueError(f"read_np_values must return 3 values, got {len(values)}")
    return tuple(int(value) for value in values)


def run_batch_check(reader, cases: Iterable[SampleCase]) -> BatchReport:
    results: list[CaseResult] = []
    for case in cases:
        actual_np = _normalize_np_values(reader.read_np_values(case.image))
        expected_defined = all(value is not None for value in case.expected_np)

        if expected_defined:
            expected_np = tuple(int(value) for value in case.expected_np)  # type: ignore[arg-type]
            passed = actual_np == expected_np
            message = "match" if passed else f"expected={expected_np} actual={actual_np}"
        else:
            passed = True
            message = "label missing; OCR call completed"

        results.append(
            CaseResult(
                image=case.image,
                expected_np=case.expected_np,
                actual_np=actual_np,
                passed=passed,
                message=message,
            )
        )

    passed_count = sum(1 for item in results if item.passed)
    return BatchReport(
        total=len(results),
        passed=passed_count,
        failed=len(results) - passed_count,
        results=results,
    )


def format_report(report: BatchReport) -> str:
    lines = [
        f"total={report.total} passed={report.passed} failed={report.failed}",
    ]
    for item in report.results:
        status = "PASS" if item.passed else "FAIL"
        lines.append(f"{status} {item.image.name} {item.message}")
    return "\n".join(lines)


def resolve_reader():
    try:
        from core.battle_ocr import BattleOcrReader
    except ImportError as exc:  # pragma: no cover - exercised by integration only
        raise RuntimeError(
            "core.battle_ocr.BattleOcrReader is not available yet. "
            "Implement BattleOcrReader.read_np_values(image_path) -> list[int]."
        ) from exc

    return BattleOcrReader()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch-check offline NP OCR samples against the future reader.",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="Path to the JSONL sample manifest.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cases = load_sample_cases(args.manifest)
    reader = resolve_reader()
    report = run_batch_check(reader, cases)
    print(format_report(report))
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
