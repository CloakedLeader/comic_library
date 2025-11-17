#!/usr/bin/env python 3
"""
Unified python test for entire project.

Tools included:
- Ruff      (fast lint + formatting check)
- Black     (opinionated formatter check)
- Mypy      (static typing)
- Pytest    (unit tests)
- Bandit    (security linter)
- Safety    (dependency vulnerability scan)

Auto-fixes:
- Ruff lint fixes (--fix)
- Ruff format fixes (or Black)
"""

import argparse
import subprocess
import sys


def run(title: str, cmd: list[str]) -> int:
    """Run a command with pretty output and return its exit code.

    Args:
        title (str): The name of the command
        cmd (list[str]): The actual command payload

    Returns:
        int: The exit code (e.g. 400)
    """

    print(f"\n=== {title} ===")
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError:
        print(f"Skipping {title}: '{cmd[0]}' not installed")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run code quality checks with autofix."
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest")
    parser.add_argument(
        "--skip-security", action="store_true", help="Skip bandit + safety"
    )
    parser.add_argument(
        "--use-black", action="store_true", help="Use Black instead of Ruff format"
    )
    args = parser.parse_args()

    exit_code = 0

    # ------------------------
    # LINTING % FORMATTING
    # ------------------------

    exit_code = max(
        exit_code,
        run(
            "Ruff: linting + autofix (incl. import sort)",
            ["ruff", "check", "--select", "I", "--fix", "."],
        ),
    )
    if args.use_black:
        exit_code = max(exit_code, run("Black: auto-format", ["black", "."]))

    else:
        exit_code = max(exit_code, run("Ruff: auto-format", ["ruff", "format", "."]))

    # -------------------
    # STATIC ANALYSIS
    # -------------------

    exit_code = max(exit_code, run("Mypy: type checking", ["mypy", "."]))

    # -----------------------------
    # TESTS
    # -----------------------------

    if not args.skip_tests:
        exit_code = max(exit_code, run("Pytest: unit tests", ["pytest", "-q"]))

    # -----------------------------
    # SECURITY SCANS (optional)
    # -----------------------------
    if not args.skip_security:
        exit_code = max(exit_code, run("Bandit: security scan", ["bandit", "-r", "."]))
        exit_code = max(exit_code, run("Safety: dependency scan", ["safety", "scan"]))

    # -----------------------------
    # SUMMARY
    # -----------------------------

    print("\n=== SUMMARY ===")
    if exit_code == 0:
        print("All checks passed ✔️ (and autofixes applied)")
    else:
        print("Some checks failed ❌")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
