"""Tests for GET /api/v1/version, the build the header names.

The build id and time come from the environment the process was started with, so each
test builds its own app after setting it; nothing here touches the database.
"""

from fastapi.testclient import TestClient

from app.main import create_app

BUILD_ID = "a1b2c3d"
BUILD_TIME = "2026-09-28T18:44:33Z"


def get_version(monkeypatch, **env):
    """Start an app under the given `TA_*` environment and return its /version response."""
    for name in ("TA_BUILD_ID", "TA_BUILD_TIME"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return TestClient(create_app()).get("/api/v1/version")


def test_version_reports_the_build_id_and_time_as_given(monkeypatch):
    """The id is passed through untouched and the time is the build instant, with its Z."""
    response = get_version(monkeypatch, TA_BUILD_ID=BUILD_ID, TA_BUILD_TIME=BUILD_TIME)

    assert response.status_code == 200
    assert response.json() == {"version": BUILD_ID, "built_at": BUILD_TIME}


def test_version_without_a_build_id_is_dev_with_no_time(monkeypatch):
    """A dev run has neither: the id reads `dev` and the time is null rather than empty."""
    response = get_version(monkeypatch)

    assert response.status_code == 200
    assert response.json() == {"version": "dev", "built_at": None}


def test_version_accepts_a_release_name_as_the_id(monkeypatch):
    """The id is opaque — a release name is shown exactly as a short sha would be."""
    response = get_version(monkeypatch, TA_BUILD_ID="v1.4.0", TA_BUILD_TIME=BUILD_TIME)

    assert response.json() == {"version": "v1.4.0", "built_at": BUILD_TIME}


def test_version_with_an_id_but_no_time_leaves_the_time_null(monkeypatch):
    """An image built without BUILD_TIME still names its build; only the date is missing."""
    response = get_version(monkeypatch, TA_BUILD_ID=BUILD_ID)

    assert response.json() == {"version": BUILD_ID, "built_at": None}
