from pathlib import Path

from fastapi.testclient import TestClient

from app.metadata import APP_VERSION


def test_pages_use_central_application_version(client: TestClient) -> None:
    response = client.get("/record")

    assert response.status_code == 200
    assert f"recorder.js?v={APP_VERSION}" in response.text
    assert f"styles.css?v={APP_VERSION}" in response.text


def test_build_definitions_do_not_duplicate_release_version() -> None:
    project_root = Path(__file__).resolve().parent.parent

    assert APP_VERSION not in (project_root / "interview_loom.spec").read_text()
    assert APP_VERSION not in (
        project_root / "packaging/windows/InterviewLoom.iss"
    ).read_text()
    assert APP_VERSION not in (
        project_root / "desktop/macos/Info.plist"
    ).read_text()
