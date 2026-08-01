#!/usr/bin/env python3
# COSTAS_VERIFIER_TESTS_V1
"""Cross-test both Costas verifiers against test_cases.json.

No third-party packages are required.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path
from typing import Any

from independent_verifier import verify_permutation as verify_independent
from reference_verifier import verify_permutation as verify_reference


def _normalize_pair(pair: list[list[int]]) -> tuple[tuple[int, int], tuple[int, int]]:
    return tuple(tuple(point) for point in pair)  # type: ignore[return-value]


def _normalize_collision(collision: dict[str, Any]) -> tuple[
    tuple[int, int], frozenset[tuple[tuple[int, int], tuple[int, int]]]
]:
    vector = tuple(collision["vector"])
    pairs = frozenset(_normalize_pair(pair) for pair in collision["point_pairs"])
    return vector, pairs  # type: ignore[return-value]


def _collision_set(report: dict[str, Any]) -> set[
    tuple[tuple[int, int], frozenset[tuple[tuple[int, int], tuple[int, int]]]]
]:
    return {_normalize_collision(item) for item in report["duplicate_vectors"]}


def _assert_expected(
    case: dict[str, Any],
    report: dict[str, Any],
    verifier_label: str,
) -> list[str]:
    errors: list[str] = []
    expected = case["expected"]

    for key in ("valid_input", "is_permutation", "is_costas", "order", "error_code"):
        if key in expected and report.get(key) != expected[key]:
            errors.append(
                f"{case['id']} [{verifier_label}]: {key}="
                f"{report.get(key)!r}, expected {expected[key]!r}"
            )

    exact_collision = expected.get("must_report_collision")
    if exact_collision is not None:
        wanted_vector = tuple(exact_collision["vector"])
        wanted_pairs = frozenset(
            _normalize_pair(pair) for pair in exact_collision["point_pairs"]
        )
        found = False
        for collision in report["duplicate_vectors"]:
            vector, pairs = _normalize_collision(collision)
            if vector == wanted_vector and wanted_pairs.issubset(pairs):
                found = True
                break
        if not found:
            errors.append(
                f"{case['id']} [{verifier_label}]: required collision not reported"
            )

    if expected.get("must_report_at_least_one_collision"):
        if not report["duplicate_vectors"]:
            errors.append(
                f"{case['id']} [{verifier_label}]: expected at least one collision"
            )

    return errors


def _cross_compare(
    case_id: str,
    reference: dict[str, Any],
    independent: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    comparable = (
        "order",
        "valid_input",
        "is_permutation",
        "is_costas",
        "error_code",
        "duplicate_vector_count",
        "duplicate_pair_occurrence_excess",
        "permutation_sha256",
    )
    for key in comparable:
        if reference.get(key) != independent.get(key):
            errors.append(
                f"{case_id} [cross-check]: {key} differs: "
                f"{reference.get(key)!r} vs {independent.get(key)!r}"
            )

    if _collision_set(reference) != _collision_set(independent):
        errors.append(f"{case_id} [cross-check]: collision reports differ")
    return errors


def run_json_cases(path: Path) -> tuple[int, list[str]]:
    with path.open("r", encoding="utf-8") as stream:
        document = json.load(stream)

    if document.get("marker") != "COSTAS_TEST_CASES_V1":
        return 0, ["test case marker is missing or incorrect"]

    failures: list[str] = []
    cases = document.get("cases")
    if not isinstance(cases, list):
        return 0, ["'cases' must be an array"]

    for case in cases:
        reference = verify_reference(case.get("input"))
        independent = verify_independent(case.get("input"))
        failures.extend(_assert_expected(case, reference, "reference"))
        failures.extend(_assert_expected(case, independent, "independent"))
        failures.extend(_cross_compare(case["id"], reference, independent))

    return len(cases), failures


def exhaustive_cross_check(max_order: int) -> tuple[int, list[str]]:
    checked = 0
    failures: list[str] = []
    for order in range(1, max_order + 1):
        for permutation in itertools.permutations(range(1, order + 1)):
            candidate = list(permutation)
            reference = verify_reference(candidate)
            independent = verify_independent(candidate)
            checked += 1
            mismatch = _cross_compare(
                f"exhaustive_n{order}_{candidate}", reference, independent
            )
            if mismatch:
                failures.extend(mismatch)
                return checked, failures
    return checked, failures


def randomized_cross_check(
    samples: int,
    max_order: int,
    seed: int,
) -> tuple[int, list[str]]:
    generator = random.Random(seed)
    failures: list[str] = []

    for index in range(samples):
        order = generator.randint(1, max_order)
        candidate = list(range(1, order + 1))
        generator.shuffle(candidate)
        reference = verify_reference(candidate)
        independent = verify_independent(candidate)
        mismatch = _cross_compare(
            f"random_{index}_n{order}", reference, independent
        )
        if mismatch:
            failures.extend(mismatch)
            return index + 1, failures

    return samples, failures


def build_parser() -> argparse.ArgumentParser:
    default_cases = Path(__file__).with_name("test_cases.json")
    parser = argparse.ArgumentParser(description="Test both Costas verifiers.")
    parser.add_argument("--cases", type=Path, default=default_cases)
    parser.add_argument(
        "--exhaustive-max-order",
        type=int,
        default=7,
        help="Cross-check every permutation through this order (default: 7).",
    )
    parser.add_argument(
        "--random-samples",
        type=int,
        default=1000,
        help="Random cross-checks through order 32 (default: 1000).",
    )
    parser.add_argument("--random-seed", type=int, default=20260801)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    failures: list[str] = []

    try:
        json_count, json_failures = run_json_cases(args.cases)
        failures.extend(json_failures)

        exhaustive_count, exhaustive_failures = exhaustive_cross_check(
            args.exhaustive_max_order
        )
        failures.extend(exhaustive_failures)

        random_count, random_failures = randomized_cross_check(
            args.random_samples, 32, args.random_seed
        )
        failures.extend(random_failures)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"TEST ERROR: {exc}", file=sys.stderr)
        return 3

    summary = {
        "test_cases_file": str(args.cases),
        "json_cases_checked": json_count,
        "exhaustive_permutations_checked": exhaustive_count,
        "random_permutations_checked": random_count,
        "random_seed": args.random_seed,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
