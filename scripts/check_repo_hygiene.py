"""Fail if generated caches, virtual environments, or secrets are tracked."""

from __future__ import annotations

import subprocess
import sys

FORBIDDEN_PARTS = {
    ".cache",
    ".paddlex_cache",
    ".paddle_home",
    ".venv",
    "__pycache__",
}


def main() -> int:
    tracked = (
        subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    violations = []

    for filename in filter(None, tracked):
        normalized_parts = filename.replace("\\", "/").split("/")
        if (
            FORBIDDEN_PARTS.intersection(normalized_parts)
            or normalized_parts[-1] == ".env"
            or filename.lower().endswith((".pyc", ".pyo"))
        ):
            violations.append(filename)

    if violations:
        print("Generated or sensitive files must not be tracked:", file=sys.stderr)
        print("\n".join(f"  {path}" for path in violations), file=sys.stderr)
        return 1

    print("Repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
