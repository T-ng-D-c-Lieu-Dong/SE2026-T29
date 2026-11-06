"""AI-generated unit test (kept only as evidence for VT-115 risk; NOT on the submitted
branch). Prompt: "write unit tests for DraftService". It mirrors the implementation:
the repository is mocked, so the stale-revision rule itself is never exercised."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain import StaleDraftRevision
from app.services.drafts import DraftService


async def test_save_returns_repository_result() -> None:
    repo = AsyncMock()
    repo.save_if_newer.return_value = SimpleNamespace(revision=2)
    assert (await DraftService(repo).save(uuid4(), 2, "a", None)).revision == 2


async def test_save_raises_stale_when_repository_returns_none() -> None:
    repo = AsyncMock()
    repo.save_if_newer.return_value = None
    repo.get.return_value = SimpleNamespace(revision=5)
    with pytest.raises(StaleDraftRevision):
        await DraftService(repo).save(uuid4(), 4, "a", None)
    repo.save_if_newer.assert_awaited_once()
