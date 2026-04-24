import subprocess
import sys


def run_step(name: str, command: list[str]) -> None:
    print(f"\n {name}...")
    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"{name} failed")
        sys.exit(result.returncode)


def main() -> None:
    print("Running pre-push checks...")

    # 1. Type checking
    run_step("Type checking (mypy)", ["mypy", "."])

    # 2. Docstring coverage
    run_step(
        "Docstring coverage (interrogate)",
        ["interrogate", "-q", "--fail-under", "80", "."],
    )

    # 3. Tests
    run_step("Running tests (pytest)", ["pytest", "-q"])

    print("\n All pre-push checks passed!")


if __name__ == "__main__":
    main()
