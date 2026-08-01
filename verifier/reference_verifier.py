#!/usr/bin/env python3
# COSTAS_REFERENCE_VERIFIER_V1
"""Readable reference verifier for 1-based Costas permutations.

Core algorithm:
    Enumerate every unordered pair of points (i, p[i]) and reject any
    repeated displacement vector (dx, dy).

The implementation uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

VERIFIER_NAME = "reference_verifier"
VERIFIER_VERSION = "1.0.0"

EXIT_COSTAS = 0
EXIT_NOT_COSTAS = 1
EXIT_INVALID_INPUT = 2
EXIT_RUNTIME_ERROR = 3


def _base_result(order: int | None) -> dict[str, Any]:
    return {
        "verifier": VERIFIER_NAME,
        "verifier_version": VERIFIER_VERSION,
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


def _permutation_hash(permutation: list[int]) -> str:
    canonical = json.dumps(
        permutation, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_permutation(permutation: Any) -> tuple[dict[str, Any], list[int] | None]:
    """Validate that input is a non-empty 1-based permutation."""
    order = len(permutation) if isinstance(permutation, list) else None
    result = _base_result(order)

    if not isinstance(permutation, list):
        result["error_code"] = "input_not_array"
        result["error_message"] = "Input must be a JSON array."
        return result, None

    if not permutation:
        result["error_code"] = "empty_permutation"
        result["error_message"] = "Permutation must contain at least one value."
        return result, None

    # bool is a subclass of int in Python, so use type(value) is int.
    if any(type(value) is not int for value in permutation):
        result["error_code"] = "non_integer_element"
        result["error_message"] = "Every permutation element must be an integer, not bool/float/string."
        return result, None

    n = len(permutation)
    if any(value < 1 for value in permutation):
        result["error_code"] = "not_a_1_based_permutation"
        result["error_message"] = f"Values must be exactly the integers 1 through {n}."
        return result, None

    if sorted(permutation) != list(range(1, n + 1)):
        result["error_code"] = "not_a_permutation"
        result["error_message"] = f"Values must be exactly the integers 1 through {n}, each once."
        return result, None

    result["valid_input"] = True
    result["is_permutation"] = True
    result["permutation_sha256"] = _permutation_hash(permutation)
    return result, permutation


def verify_permutation(permutation: Any) -> dict[str, Any]:
    """Return a JSON-serializable verification report."""
    result, values = _validate_permutation(permutation)
    if values is None:
        return result

    # Map each displacement vector to every point pair that realizes it.
    vector_to_pairs: dict[tuple[int, int], list[list[list[int]]]] = {}
    n = len(values)

    for left in range(n):
        point_left = [left + 1, values[left]]
        for right in range(left + 1, n):
            point_right = [right + 1, values[right]]
            vector = (right - left, values[right] - values[left])
            vector_to_pairs.setdefault(vector, []).append([point_left, point_right])

    duplicates: list[dict[str, Any]] = []
    excess = 0
    for vector in sorted(vector_to_pairs):
        point_pairs = vector_to_pairs[vector]
        if len(point_pairs) > 1:
            duplicates.append(
                {
                    "vector": [vector[0], vector[1]],
                    "multiplicity": len(point_pairs),
                    "point_pairs": point_pairs,
                }
            )
            excess += len(point_pairs) - 1

    result["duplicate_vectors"] = duplicates
    result["duplicate_vector_count"] = len(duplicates)
    result["duplicate_pair_occurrence_excess"] = excess
    result["is_costas"] = not duplicates
    return result


def _extract_permutation(document: Any) -> Any:
    """Accept a raw array or a candidate object containing 'permutation'."""
    if isinstance(document, dict) and "permutation" in document:
        return document["permutation"]
    return document


def _parse_inline_permutation(text: str) -> Any:
    """Parse a JSON array; also accept a plain comma-separated integer list."""
    try:
        return _extract_permutation(json.loads(text))
    except json.JSONDecodeError:
        try:
            return [int(piece.strip()) for piece in text.split(",") if piece.strip()]
        except ValueError as exc:
            raise ValueError(
                "--permutation must be a JSON array or comma-separated integers"
            ) from exc


def _load_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return _extract_permutation(json.load(handle))


def _human_output(report: dict[str, Any]) -> str:
    lines = [
        f"Verifier: {report['verifier']} {report['verifier_version']}",
        f"Order: {report['order']}",
        f"Valid input: {report['valid_input']}",
        f"Permutation: {report['is_permutation']}",
        f"Costas: {report['is_costas']}",
    ]
    if report["error_code"]:
        lines.append(f"Error: {report['error_code']} — {report['error_message']}")
    if report["duplicate_vectors"]:
        lines.append(f"Duplicate vectors: {report['duplicate_vector_count']}")
        for collision in report["duplicate_vectors"]:
            lines.append(
                f"  {collision['vector']}: {collision['point_pairs']}"
            )
    return "\n".join(lines)


def self_test() -> bool:
    tests = [
        ([1], True),
        ([1, 2], True),
        ([2, 1], True),
        ([1, 3, 2], True),
        ([1, 2, 4, 3], True),
        ([1, 2, 3], False),
        ([1, 3, 2, 4], False),
    ]
    for permutation, expected in tests:
        report = verify_permutation(permutation)
        if report["is_costas"] is not expected:
            return False

    invalid_tests = [
        ([], "empty_permutation"),
        ([1, 1, 3], "not_a_permutation"),
        ([0, 1, 2], "not_a_1_based_permutation"),
        ([1, "2", 3], "non_integer_element"),
        ([1, True, 3], "non_integer_element"),
        (None, "input_not_array"),
    ]
    for permutation, expected_error in invalid_tests:
        report = verify_permutation(permutation)
        if report["error_code"] != expected_error:
            return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a 1-based Costas permutation by displacement vectors."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--permutation",
        help='JSON array such as "[1,2,4,3]" or comma-separated integers.',
    )
    source.add_argument(
        "--input",
        type=Path,
        help="JSON file containing either an array or an object with a permutation field.",
    )
    parser.add_argument(
        "--output",
        choices=("json", "human"),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in smoke tests and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.self_test:
        passed = self_test()
        payload = {
            "verifier": VERIFIER_NAME,
            "verifier_version": VERIFIER_VERSION,
            "self_test": "PASS" if passed else "FAIL",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
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
        permutation = (
            _parse_inline_permutation(args.permutation)
            if args.permutation is not None
            else _load_file(args.input)
        )
        report = verify_permutation(permutation)
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

    if args.output == "human":
        print(_human_output(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if not report["valid_input"]:
        return EXIT_INVALID_INPUT
    return EXIT_COSTAS if report["is_costas"] else EXIT_NOT_COSTAS


if __name__ == "__main__":
    raise SystemExit(main())
