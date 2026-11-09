from datetime import UTC, datetime, timedelta

from app.api.version import version
from app.config import Settings


async def test_version_exposes_environment_and_inactive_fault() -> None:
    payload = await version(
        Settings(
            release="v0.2.0",
            commit_sha="abc1234",
            deployment_environment="demo",
        )
    )

    assert payload == {
        "release": "v0.2.0",
        "commit_sha": "abc1234",
        "environment": "demo",
        "fault_active": False,
    }


async def test_version_reports_only_unexpired_fault_as_active() -> None:
    payload = await version(
        Settings(
            fault_mode="error",
            fault_until=datetime.now(UTC) + timedelta(minutes=5),
        )
    )

    assert payload["fault_active"] is True
