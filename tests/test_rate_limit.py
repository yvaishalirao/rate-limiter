import uuid
import httpx
import pytest

BASE_URL = "http://localhost:8000"
LIMIT = 5


def uid(prefix: str = "") -> str:
    """Unique user_id per test call — prevents state bleed between tests."""
    return f"{prefix}{uuid.uuid4().hex}"


async def post(client: httpx.AsyncClient, user_id: str):
    return await client.post("/check-rate-limit", json={"user_id": user_id})


@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL) as c:
        yield c


# ---------------------------------------------------------------------------
# Core allowed / denied behaviour
# ---------------------------------------------------------------------------

async def test_first_request_allowed(client):
    resp = await post(client, uid("t1_"))
    assert resp.status_code == 200
    assert resp.json()["allowed"] is True


async def test_remaining_decrements(client):
    user = uid("decr_")
    remainders = []
    for _ in range(3):
        resp = await post(client, user)
        remainders.append(resp.json()["remaining"])
    assert remainders == [4, 3, 2]


async def test_nth_request_allowed_remaining_zero(client):
    user = uid("nth_")
    resp = None
    for _ in range(LIMIT):
        resp = await post(client, user)
    assert resp.status_code == 200
    assert resp.json()["remaining"] == 0


async def test_n_plus_one_denied(client):
    user = uid("deny_")
    for _ in range(LIMIT):
        await post(client, user)
    resp = await post(client, user)
    assert resp.status_code == 429


async def test_denied_never_200(client):
    user = uid("nev200_")
    for _ in range(LIMIT):
        await post(client, user)
    resp = await post(client, user)
    assert resp.status_code != 200  # INV-5


async def test_denied_response_body(client):
    user = uid("body_")
    for _ in range(LIMIT):
        await post(client, user)
    resp = await post(client, user)
    assert resp.status_code == 429
    body = resp.json()["detail"]
    assert body["allowed"] is False
    assert body["remaining"] == 0


# ---------------------------------------------------------------------------
# Multi-user isolation  (INV-2)
# ---------------------------------------------------------------------------

async def test_two_users_independent(client):
    user_a = uid("userA_")
    user_b = uid("userB_")
    for _ in range(LIMIT):
        await post(client, user_a)
    resp = await post(client, user_b)
    assert resp.status_code == 200
    assert resp.json()["remaining"] == LIMIT - 1  # userB untouched


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

async def test_missing_user_id_422(client):
    resp = await client.post("/check-rate-limit", json={})
    assert resp.status_code == 422


async def test_empty_user_id(client):
    # Empty string is a valid identifier — hashed like any other (INV-2)
    resp = await post(client, "")
    assert resp.status_code == 200


async def test_long_user_id(client):
    # 10 000-char identifier must not crash the service
    resp = await post(client, "x" * 10_000)
    assert resp.status_code == 200


async def test_special_chars_user_id(client):
    # Redis injection chars must be absorbed by make_key() hashing (INV-8)
    resp = await post(client, "a*?[b")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

async def test_health_endpoint(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
