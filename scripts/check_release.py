"""Validate release metadata and reproducible runtime dependencies."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
ADDON = ROOT / "engelsoft_bacstac"


def main() -> None:
    """Fail when release metadata is inconsistent or dependencies float."""
    config = yaml.safe_load((ADDON / "config.yaml").read_text(encoding="utf-8"))
    yaml.safe_load((ROOT / ".github" / "workflows" / "build.yaml").read_text(encoding="utf-8"))
    version = str(config["version"])
    changelog = (ADDON / "CHANGELOG.md").read_text(encoding="utf-8-sig")
    if not re.search(rf"^# {re.escape(version)}\s*$", changelog, re.MULTILINE):
        raise SystemExit(f"CHANGELOG.md has no release heading for {version}")

    requirements = (ADDON / "requirements.txt").read_text(encoding="utf-8").splitlines()
    floating = [line for line in requirements if line.strip() and "==" not in line]
    if floating:
        raise SystemExit(f"Runtime dependencies must use exact pins: {floating}")

    dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
    if "BACSTAC_VERSION=${BUILD_VERSION}" not in dockerfile:
        raise SystemExit("Dockerfile does not pass BUILD_VERSION to the application")

    print(f"Release metadata for {version} is consistent.")


if __name__ == "__main__":
    main()
