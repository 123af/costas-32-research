#!/usr/bin/env python3
# COSTAS_INDEPENDENT_VERIFIER_V1
"""Independent verifier for 1-based Costas permutations.

Core algorithm:
    Build each row of the difference triangle separately. For a fixed
    horizontal distance d, all values p[i+d] - p[i] must be distinct.

This file intentionally does not import the reference verifier.
It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

VERIFIER_NAME = "independent_verifier"
VERIFIER_VERSION = "1.0.0"

EXIT_COSTAS = 0
EXIT_NOT_COSTAS = 1
EXIT_INVALID_INPUT = 2
EXIT_RUNTIME_ERROR = 3


def _new_report(order: int | None) -> dict[str, Any]:
    return {
        "verifier": VERIFIER_NAME,
        "verifier_version": VERIFIER_VERSION,
        "algorithm": "difference_triangle",
        "indexing": "1-based",
        "order": order,
        "valid_input": False,
        "is_permutation": False,
        "is_costas": False,
        "error_code": None,
        "error_message": None,
        "duplicate_vector_count": 0,
        "duplicate_pair_occurrence_excess": 0,
        "duplicate_vectors": [],
        "permutation_sha256": None,
    }


def _sha256(values: list[int]) -> str:
    compact = json.dumps(values, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(compact).hexdigest()


def _check_input(candidate: Any) -> tuple[dict[str, Any], tuple[int, ...] | None]:
    order = len(candidate) if isinstance(candidate, list) else None
    report = _new_report(order)

    if not isinstance(candidate, list):
        report["error_code"] = "input_not_array"
        report["error_message"] = "Input must be a JSON array."
        return report, None

    if len(candidate) == 0:
        report["error_code"] = "empty_permutation"
        report["error_message"] = "Permutation must not be empty."
        return report, None

    for item in candidate:
        if type(item) is not int:
            report["error_code"] = "non_integer_element"
            report["error_message"] = "Permutation values must be genuine integers."
            return report, None

    n = len(candidate)
    if min(candidate) < 1:
        report["error_code"] = "not_a_1_based_permutation"
        report["error_message"] = f"Expected every integer from 1 through {n}."
        return report, None

    # Count occurrences instead of sorting, to keep validation independent.
    counts = [0] * (n + 1)
    for item in candidate:
        if item > n:
            report["error_code"] = "not_a_permutation"
            report["error_message"] = f"Expected every integer from 1 through {n}."
            return report, None
        counts[item] += 1

    if any(count != 1 for count in counts[1:]):
        report["error_code"] = "not_a_permutation"
        report["error_message"] = f"Expected every integer from 1 through {n}, exactly once."
        return report, None

    report["valid_input"] = True
    report["is_permutation"] = True
    report["permutation_sha256"] = _sha256(candidate)
    return report, tuple(candidate)


def verify_permutation(permutation: Any) -> dict[str, Any]:
    """Verify through uniqueness of each difference-triangle row."""
    report, values = _check_input(permutation)
    if values is None:
        return report

    n = len(values)
    collisions: list[dict[str, Any]] = []
    total_excess = 0

    for distance in range(1, n):
        starts_by_difference: dict[int, list[int]] = {}

        for start in range(0, n - distance):
            vertical_difference = values[start + distance] - values[start]
            starts_by_difference.setdefault(vertical_difference, []).append(start)

        for vertical_difference in sorted(starts_by_difference):
            starts = starts_by_difference[vertical_difference]
            if len(starts) <= 1:
                continue

            point_pairs: list[list[list[int]]] = []
            for start in starts:
                point_pairs.append(
                    [
                        [start + 1, values[start]],
                        [start + distance + 1, values[start + distance]],
                    ]
                )

            collisions.append(
                {
                    "vector": [distance, vertical_difference],
                    "multiplicity": len(starts),
                    "point_pairs": point_pairs,
                }
            )
            total_excess += len(starts) - 1

    report["duplicate_vectors"] = collisions
    report["duplicate_vector_count"] = len(collisions)
    report["duplicate_pair_occurrence_excess"] = total_excess
    report["is_costas"] = len(collisions) == 0
    return report


def _read_inline(text: str) -> Any:
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        try:
            decoded = [int(part.strip()) for part in text.split(",") if part.strip()]
        except ValueError as exc:
            raise ValueError(
                "--permutation must be JSON or comma-separated integers"
            ) from exc
    if isinstance(decoded, dict) and "permutation" in decoded:
        return decoded["permutation"]
    return decoded


def _read_path(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        decoded = json.load(stream)
    if isinstance(decoded, dict) and "permutation" in decoded:
        return decoded["permutation"]
    return decoded


def _format_human(report: dict[str, Any]) -> str:
    text = [
        f"Verifier: {report['verifier']} {report['verifier_version']}",
        f"Algorithm: {report['algorithm']}",
        f"Order: {report['order']}",
        f"Valid input: {report['valid_input']}",
        f"Permutation: {report['is_permutation']}",
        f"Costas: {report['is_costas']}",
    ]
    if report["error_code"]:
        text.append(f"Error: {report['error_code']} — {report['error_message']}")
    for collision in report["duplicate_vectors"]:
        text.append(
            f"Collision {collision['vector']}: {collision['point_pairs']}"
        )
    return "\n".join(text)


def self_test() -> bool:
    valid = (
        [1],
        [1, 2],
        [2, 1],
        [1, 3, 2],
        [1, 2, 4, 3],
        [1, 3, 4, 2],
    )
    invalid_costas = (
        [1, 2, 3],
        [1, 2, 3, 4],
        [2, 4, 1, 3],
    )

    if any(not verify_permutation(case)["is_costas"] for case in valid):
        return False
    if any(verify_permutation(case)["is_costas"] for case in invalid_costas):
        return False

    malformed = (
        ([], "empty_permutation"),
        ([1, 1, 3], "not_a_permutation"),
        ([0, 1, 2], "not_a_1_based_permutation"),
        ([1, 2.0, 3], "non_integer_element"),
        ([1, True, 3], "non_integer_element"),
        ({"permutation": [1, 3, 2]}, "input_not_array"),
    )
    return all(
        verify_permutation(case)["error_code"] == expected
        for case, expected in malformed
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Verify a 1-based Costas permutation using its difference triangle."
    )
    source = result.add_mutually_exclusive_group()
    source.add_argument("--permutation")
    source.add_argument("--input", type=Path)
    result.add_argument("--output", choices=("json", "human"), default="json")
    result.add_argument("--self-test", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)

    if args.self_test:
        passed = self_test()
        print(
            json.dumps(
                {
                    "verifier": VERIFIER_NAME,
                    "verifier_version": VERIFIER_VERSION,
                    "self_test": "PASS" if passed else "FAIL",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_COSTAS if passed else EXIT_RUNTIME_ERROR

    if args.permutation is None and args.input is None:
        print(
            json.dumps(
                {
                    "error_code": "missing_input",
                    "error_message": "Use --permutation, --input, or --self-test.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return EXIT_RUNTIME_ERROR

    try:
        candidate = (
            _read_inline(args.permutation)
            if args.permutation is not None
            else _read_path(args.input)
        )
        report = verify_permutation(candidate)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "error_code": "input_or_runtime_error",
                    "error_message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return EXIT_RUNTIME_ERROR

    print(
        _format_human(report)
        if args.output == "human"
        else json.dumps(report, ensure_ascii=False, indent=2)
    )

    if not report["valid_input"]:
        return EXIT_INVALID_INPUT
    return EXIT_COSTAS if report["is_costas"] else EXIT_NOT_COSTAS


if __name__ == "__main__":
    raise SystemExit(main())
