"""
Run tests with coverage and print coverage percentage for app code.

Usage:
    python scripts/coverage_report.py
    python scripts/coverage_report.py --percent-only
    python scripts/coverage_report.py --min-percent 80
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


TOTAL_COVERAGE_RE = re.compile(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%\s*$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pytest coverage and print total percentage."
    )
    parser.add_argument(
        "--percent-only",
        action="store_true",
        help="Print only the numeric coverage percentage.",
    )
    parser.add_argument(
        "--min-percent",
        type=int,
        default=80,
        help="Fail (exit 1) when coverage is below this percentage. Default: 80.",
    )
    return parser.parse_args()


def run_pytest_with_coverage(project_root: Path) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--cov=app",
        "--cov-report=term-missing",
        "-q",
    ]
    return subprocess.run(
        command,
        cwd=str(project_root),
        text=True,
        capture_output=True,
    )


def extract_total_coverage(output: str) -> int | None:
    match = TOTAL_COVERAGE_RE.search(output)
    if not match:
        return None
    return int(match.group(1))


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]

    result = run_pytest_with_coverage(project_root)
    full_output = (result.stdout or "") + (result.stderr or "")

    # Always show pytest output first unless explicitly asked for only percent.
    if not args.percent_only:
        if full_output.strip():
            print(full_output.rstrip())

    coverage_percent = extract_total_coverage(full_output)
    if coverage_percent is None:
        print("Could not parse TOTAL coverage percentage from pytest output.")
        return 2

    if args.percent_only:
        print(coverage_percent)
    else:
        print(f"\nCoverage percentage (app): {coverage_percent}%")

    # Preserve test failure signal first.
    if result.returncode != 0:
        return result.returncode

    # Enforce minimum coverage threshold.
    if coverage_percent < args.min_percent:
        if not args.percent_only:
            print(
                f"Coverage gate failed: {coverage_percent}% < {args.min_percent}%"
            )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

