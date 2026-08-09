import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.metadata import APP_IDENTIFIER, APP_NAME, APP_VERSION  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def installed_packages() -> list[dict[str, str]]:
    packages = {
        distribution.metadata["Name"]: distribution.version
        for distribution in distributions()
        if distribution.metadata["Name"]
    }
    return [
        {"name": name, "version": packages[name]}
        for name in sorted(packages, key=str.casefold)
    ]


def create_manifest(
    platform_name: str,
    architecture: str,
    artifacts: list[Path],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "application": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "identifier": APP_IDENTIFIER,
        },
        "build": {
            "platform": platform_name,
            "architecture": architecture,
            "commit": os.environ.get("GITHUB_SHA", "local"),
            "created_at": datetime.now(UTC).isoformat(),
        },
        "artifacts": [
            {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in artifacts
        ],
        "python_packages": installed_packages(),
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("artifacts", nargs="+", type=Path)
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    missing = [path for path in arguments.artifacts if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing release artifacts: {missing}")
    manifest = create_manifest(
        arguments.platform,
        arguments.architecture,
        arguments.artifacts,
    )
    arguments.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
