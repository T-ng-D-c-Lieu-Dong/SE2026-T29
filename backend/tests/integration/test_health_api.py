import pytest

pytestmark = pytest.mark.integration


async def test_liveness_does_not_query_database(client) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_checks_database_and_schema(client) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database_check_ms"] >= 0


async def test_version_endpoint(client) -> None:
    response = await client.get("/api/version")

    assert response.status_code == 200
    assert set(response.json()) == {
        "release",
        "commit_sha",
        "environment",
        "fault_active",
    }
    assert response.json()["fault_active"] is False
