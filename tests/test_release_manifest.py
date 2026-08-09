from pathlib import Path

from app.metadata import APP_IDENTIFIER, APP_NAME, APP_VERSION
from scripts.create_release_manifest import create_manifest, sha256


def test_release_manifest_contains_version_and_artifact_hash(tmp_path: Path) -> None:
    artifact = tmp_path / "Interview-Loom.zip"
    artifact.write_bytes(b"release-content")

    manifest = create_manifest("macOS", "arm64", [artifact])

    assert manifest["application"] == {
        "name": APP_NAME,
        "version": APP_VERSION,
        "identifier": APP_IDENTIFIER,
    }
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    assert artifacts[0] == {
        "filename": artifact.name,
        "size_bytes": len(b"release-content"),
        "sha256": sha256(artifact),
    }
