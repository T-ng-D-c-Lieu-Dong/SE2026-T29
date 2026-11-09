from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["version"])


@router.get("/version")
async def version(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str | bool]:
    fault_active = (
        settings.fault_mode != "off"
        and settings.fault_until is not None
        and settings.fault_until.astimezone(UTC) > datetime.now(UTC)
    )
    return {
        "release": settings.release,
        "commit_sha": settings.commit_sha,
        "environment": settings.deployment_environment,
        "fault_active": fault_active,
    }
