"""VT-115 — Autosave draft: newer data must never be overwritten by an older save.

These tests are written from the acceptance criteria (docs/vt115/README.md), not from
the implementation. They only use the public HTTP contract and the persisted row, so a
refactor of the service/repository must not change them.

AC1  PUT /api/drafts/{id} with a higher revision is saved and returned (200).
AC2  A save whose revision is <= the stored revision is rejected with 409, the stored
     draft is unchanged and the response carries the current server copy.
AC3  Concurrent saves of the same draft always converge to the highest revision,
     whatever order they reach the database in.
AC4  Invalid payloads (revision < 1, name > 100 chars, naive datetime) are rejected
     with 422 and never consume a revision.
AC5  GET /api/drafts/{id} returns the latest saved draft, or 404 for an unknown id.
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

AWARE_START = datetime(2026, 12, 1, 9, 30, tzinfo=UTC).isoformat()


def body(revision: int, name: str | None = "Nguyễn Mai Hoàng Anh", starts_at=AWARE_START):
    return {"revision": revision, "customer_name": name, "starts_at": starts_at}


async def seed(client, draft_id: UUID, revision: int, name: str) -> None:
    response = await client.put(f"/api/drafts/{draft_id}", json=body(revision, name))
    assert response.status_code == 200, f"seeding draft failed: {response.status_code}"


async def wait_for_lock_waiters(factory, count: int, limit_seconds: float = 5.0) -> None:
    """Poll until `count` backends are blocked on a lock touching appointment_drafts."""
    deadline = asyncio.get_running_loop().time() + limit_seconds
    while True:
        async with factory() as session:
            waiting = await session.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE wait_event_type = 'Lock' AND query ILIKE '%appointment_drafts%'"
                )
            )
        if waiting >= count:
            return
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"expected {count} lock waiters, saw {waiting}")
        await asyncio.sleep(0.005)


async def stored_revision(factory, draft_id: UUID) -> int | None:
    async with factory() as session:
        return await session.scalar(
            text("SELECT revision FROM appointment_drafts WHERE id = :id"), {"id": draft_id}
        )


# ---------------------------------------------------------------- AC1 / AC5 happy path


async def test_tc01_first_save_creates_draft(client) -> None:
    draft_id = uuid4()

    response = await client.put(f"/api/drafts/{draft_id}", json=body(1))

    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["id"] == str(draft_id)
    assert saved["revision"] == 1
    assert saved["customer_name"] == "Nguyễn Mai Hoàng Anh"


async def test_tc02_higher_revision_replaces_whole_snapshot(client) -> None:
    draft_id = uuid4()
    await seed(client, draft_id, 1, "An")

    response = await client.put(f"/api/drafts/{draft_id}", json=body(2, "An Nguyen", None))

    assert response.status_code == 200, response.text
    fetched = (await client.get(f"/api/drafts/{draft_id}")).json()
    assert fetched["revision"] == 2
    assert fetched["customer_name"] == "An Nguyen"
    assert fetched["starts_at"] is None  # full snapshot, not a field merge


async def test_tc03_get_unknown_draft_returns_404(client) -> None:
    response = await client.get(f"/api/drafts/{uuid4()}")

    assert response.status_code == 404
    # A bare 404 would also pass when the route does not exist at all (it did on the
    # baseline commit). The domain message proves the handler ran and found nothing.
    assert response.json() == {"detail": "Draft was not found"}


# ---------------------------------------------------------------- AC2 stale writes


async def test_tc04_older_revision_is_rejected_and_does_not_overwrite(
    client, test_session_factory
) -> None:
    draft_id = uuid4()
    await seed(client, draft_id, 5, "newer text")

    stale = await client.put(f"/api/drafts/{draft_id}", json=body(4, "older text"))

    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["current"]["revision"] == 5
    assert stale.json()["detail"]["current"]["customer_name"] == "newer text"
    assert await stored_revision(test_session_factory, draft_id) == 5
    fetched = (await client.get(f"/api/drafts/{draft_id}")).json()
    assert fetched["customer_name"] == "newer text"


async def test_tc05_same_revision_retry_is_rejected_not_reapplied(client) -> None:
    """Failure path: the client's response was lost and it retries the same revision
    with different content (e.g. an old buffer). The server must keep the first write."""
    draft_id = uuid4()
    first = await client.put(f"/api/drafts/{draft_id}", json=body(3, "first write"))
    assert first.status_code == 200

    retry = await client.put(f"/api/drafts/{draft_id}", json=body(3, "retry with old buffer"))

    assert retry.status_code == 409
    assert retry.json()["detail"]["current"]["customer_name"] == "first write"


# ---------------------------------------------------------------- AC4 negative inputs


@pytest.mark.parametrize(
    ("payload", "case"),
    [
        (body(0), "revision zero"),
        (body(-1), "negative revision"),
        ({"customer_name": "x", "starts_at": None}, "missing revision"),
        (body(2, "x" * 101), "name over 100 chars"),
        (body(2, starts_at="2026-12-01T09:30:00"), "naive datetime"),
    ],
)
async def test_tc06_invalid_payload_is_rejected_without_consuming_revision(
    client, test_session_factory, payload, case
) -> None:
    draft_id = uuid4()
    await seed(client, draft_id, 1, "kept")

    response = await client.put(f"/api/drafts/{draft_id}", json=payload)

    assert response.status_code == 422, f"{case}: {response.status_code} {response.text}"
    assert await stored_revision(test_session_factory, draft_id) == 1, case


async def test_tc07_boundary_name_100_chars_is_accepted(client) -> None:
    response = await client.put(f"/api/drafts/{uuid4()}", json=body(1, "đ" * 100))

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------- AC3 concurrency


async def test_tc08_concurrent_pair_newer_always_wins_in_both_orders(
    client, test_session_factory
) -> None:
    """Two saves race; we vary which one is scheduled first and add jitter so both
    arrival orders are exercised. Final state must be the higher revision every time."""
    rng = random.Random(115)  # fixed seed -> reproducible schedule
    for iteration in range(40):
        draft_id = uuid4()
        await seed(client, draft_id, 1, "base")

        async def save(revision: int, delay: float, draft_id=draft_id):
            await asyncio.sleep(delay)
            return await client.put(
                f"/api/drafts/{draft_id}", json=body(revision, f"rev-{revision}")
            )

        older_first = iteration % 2 == 0
        jitter = rng.uniform(0, 0.003)
        older = save(2, 0 if older_first else jitter)
        newer = save(3, jitter if older_first else 0)
        responses = await asyncio.gather(older, newer)

        assert all(r.status_code in (200, 409) for r in responses), [r.text for r in responses]
        assert await stored_revision(test_session_factory, draft_id) == 3, iteration


async def test_tc09_hundred_concurrent_saves_same_draft_converge_to_max(
    client, test_session_factory
) -> None:
    """100 concurrent autosaves of one draft (revisions 1..100, shuffled)."""
    draft_id = uuid4()
    revisions = list(range(1, 101))
    random.Random(23001824).shuffle(revisions)

    responses = await asyncio.gather(
        *(client.put(f"/api/drafts/{draft_id}", json=body(rev, f"rev-{rev}")) for rev in revisions)
    )

    codes = [r.status_code for r in responses]
    assert set(codes) <= {200, 409}, codes
    assert await stored_revision(test_session_factory, draft_id) == 100
    final = (await client.get(f"/api/drafts/{draft_id}")).json()
    assert final["customer_name"] == "rev-100"
    accepted = [r.json()["revision"] for r in responses if r.status_code == 200]
    assert 100 in accepted


async def test_tc10_stale_save_waiting_on_row_lock_does_not_overwrite(
    client, test_session_factory
) -> None:
    """Deterministic interleaving: hold a row lock so both saves queue on it, then
    release. The older save is queued *after* the newer one has been decided."""
    draft_id = uuid4()
    await seed(client, draft_id, 1, "base")

    async with test_session_factory() as blocker:
        await blocker.execute(
            text("SELECT 1 FROM appointment_drafts WHERE id = :id FOR UPDATE"), {"id": draft_id}
        )
        # No fixed sleeps: wait until PostgreSQL itself reports the request queued on the
        # lock (a fixed 50 ms sleep failed 2/30 runs when compressed; evidence 08).
        newer = asyncio.create_task(client.put(f"/api/drafts/{draft_id}", json=body(7, "new")))
        await wait_for_lock_waiters(test_session_factory, 1)
        older = asyncio.create_task(client.put(f"/api/drafts/{draft_id}", json=body(6, "old")))
        await wait_for_lock_waiters(test_session_factory, 2)
        await blocker.rollback()  # release the lock

    newer_response, older_response = await asyncio.gather(newer, older)

    assert newer_response.status_code == 200
    assert older_response.status_code == 409
    assert await stored_revision(test_session_factory, draft_id) == 7


async def test_tc11_concurrent_saves_of_different_drafts_are_isolated(
    client, test_session_factory
) -> None:
    draft_ids = [uuid4() for _ in range(100)]

    responses = await asyncio.gather(
        *(
            client.put(f"/api/drafts/{d}", json=body(1, f"user-{i}"))
            for i, d in enumerate(draft_ids)
        )
    )

    assert [r.status_code for r in responses] == [200] * 100
    for index in (0, 57, 99):
        fetched = (await client.get(f"/api/drafts/{draft_ids[index]}")).json()
        assert fetched["customer_name"] == f"user-{index}"


async def test_tc12_server_clock_is_not_used_to_order_saves(client, test_session_factory) -> None:
    """A save with a later client-side timestamp but lower revision must still lose:
    ordering is by revision, never by wall-clock time."""
    draft_id = uuid4()
    await seed(client, draft_id, 9, "rev9")
    later = (datetime.now(UTC) + timedelta(days=30)).isoformat()

    response = await client.put(f"/api/drafts/{draft_id}", json=body(8, "rev8", later))

    assert response.status_code == 409
    assert await stored_revision(test_session_factory, draft_id) == 9


# ---------------------------------------------------------------- added after mutation M4


@pytest.mark.parametrize(
    ("revision", "expected"),
    [
        (2**53 - 1, 200),  # largest revision a browser can send exactly
        (2**53, 422),  # would silently lose precision in JavaScript
        (0, 422),  # brand-new draft: must be a 422, not a DB CHECK violation (500)
    ],
)
async def test_tc13_revision_boundaries_on_new_draft(
    client, test_session_factory, revision, expected
) -> None:
    draft_id = uuid4()

    response = await client.put(f"/api/drafts/{draft_id}", json=body(revision))

    assert response.status_code == expected, response.text
    stored = await stored_revision(test_session_factory, draft_id)
    assert stored == (revision if expected == 200 else None)
