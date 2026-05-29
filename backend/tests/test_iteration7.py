"""GameScout backend tests — Iteration 7.

Coverage:
- Emojis: GET /api/emojis (public, returns {basic, custom}), POST/DELETE /api/admin/emojis with admin ACL.
- Message reactions: DM + community toggle, ACL (stranger 403), `mine` flag in aggregated GET.
- Review reactions: toggle + public GET (mine=False unauthenticated).
- Review likes: toggle, count, mine.
- Review comments: list public ASC order, post requires verified user, delete by author or admin.
- DM pagination with `before` cursor.
- Community pagination with `before` cursor.
- Messages return `reactions` field.
- WebSocket /api/ws/chat/dm/{friend} — handshake 4401 (no auth), 4403 (not friend), ping/pong, broadcast on POST.
- WebSocket /api/ws/chat/community/{cid} — 4403 if non-member, broadcast to member.
- Verification gating on react/like/comment endpoints.
- Quick regression of iter 6 essentials: gmail-only register, admin login, /games/top bayesian.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
import websockets
import websockets.exceptions as wsexc
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gamescout-reviews.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
WS_BASE = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "matheusvittore670@gmail.com"
ADMIN_PASSWORD = "admin123"

REVIEW_CATEGORIES = ["graphics", "story", "tutorial", "gameplay", "audio", "performance", "fun"]


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mdb():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


def _gmail(prefix="alice"):
    return f"{prefix}_i7_{uuid.uuid4().hex[:8]}@gmail.com"


def _register(email, password="Password123!", name="I7 User"):
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": password, "name": name})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return s


def _verify(session, mdb, user_id):
    rec = mdb.email_verifications.find_one({"user_id": user_id})
    assert rec, f"No verification code for {user_id}"
    r = session.post(f"{API}/auth/verify-email", json={"code": rec["code"]})
    assert r.status_code == 200, f"verify failed: {r.status_code} {r.text}"


def _new_verified(mdb, prefix="alice"):
    email = _gmail(prefix)
    s = _register(email)
    uid = s.get(f"{API}/auth/me").json()["user_id"]
    _verify(s, mdb, uid)
    s._uid = uid
    s._email = email
    return s


def _new_unverified(prefix="alice"):
    email = _gmail(prefix)
    s = _register(email)
    uid = s.get(f"{API}/auth/me").json()["user_id"]
    s._uid = uid
    s._email = email
    return s


def _be_friends(a, b):
    r = a.post(f"{API}/friends/request/{b._uid}")
    assert r.status_code == 200, r.text
    r = b.post(f"{API}/friends/accept/{a._uid}")
    assert r.status_code == 200, r.text


def _any_game_id():
    r = requests.get(f"{API}/games", params={"limit": 1})
    return r.json()[0]["game_id"]


def _post_review(session, game_id, rating=8, note="Review TEST_i7."):
    payload = {
        "rating": rating, "hours_played": 12, "recommends": True,
        "platform": "pc", "note": note,
        **{c: rating for c in REVIEW_CATEGORIES},
    }
    # Try delete a prior review for this user/game first
    r = session.post(f"{API}/games/{game_id}/reviews", json=payload)
    if r.status_code in (400, 409):
        # Already reviewed → fetch existing
        existing = requests.get(f"{API}/games/{game_id}/reviews").json()
        my_uid = session.get(f"{API}/auth/me").json()["user_id"]
        for rv in existing:
            if rv.get("user_id") == my_uid:
                return rv
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def alice(mdb):
    return _new_verified(mdb, "alice")


@pytest.fixture(scope="session")
def bob(mdb, alice):
    b = _new_verified(mdb, "bob")
    _be_friends(alice, b)
    return b


@pytest.fixture(scope="session")
def carol(mdb):
    # Not friend of alice/bob
    return _new_verified(mdb, "carol")


# ---------------------------------------------------------------------------
# 1. Emojis endpoints
# ---------------------------------------------------------------------------
class TestEmojis:
    def test_emojis_public(self):
        r = requests.get(f"{API}/emojis")
        assert r.status_code == 200
        body = r.json()
        assert "basic" in body and "custom" in body
        assert isinstance(body["basic"], list) and len(body["basic"]) >= 9
        for need in ["👌", "❤️", "🤣", "🔥", "🎮"]:
            assert need in body["basic"]
        assert isinstance(body["custom"], list)

    def test_admin_can_add_and_remove_custom(self, admin_session):
        emoji = f"🎲{uuid.uuid4().hex[:2]}"
        # Note: emoji length capped at 16 — must use short unicode
        emoji = "🎲"
        # Remove any pre-existing same emoji to keep idempotent
        existing = requests.get(f"{API}/emojis").json().get("custom", [])
        for e in existing:
            if e["emoji"] == emoji:
                admin_session.delete(f"{API}/admin/emojis/{e['emoji_id']}")
        r = admin_session.post(f"{API}/admin/emojis", json={"emoji": emoji, "name": "dado"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["emoji"] == emoji
        eid = body["emoji_id"]
        # Now visible publicly
        emjs = requests.get(f"{API}/emojis").json()
        assert any(e["emoji_id"] == eid for e in emjs["custom"])
        # Delete
        r2 = admin_session.delete(f"{API}/admin/emojis/{eid}")
        assert r2.status_code == 200

    def test_non_admin_cannot_add_emoji(self, alice):
        r = alice.post(f"{API}/admin/emojis", json={"emoji": "🐉", "name": "drag"})
        assert r.status_code == 403

    def test_unauth_cannot_add_emoji(self):
        r = requests.post(f"{API}/admin/emojis", json={"emoji": "🐲"})
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 2. Message reactions (DM)
# ---------------------------------------------------------------------------
class TestDMReactions:
    def test_sender_and_recipient_can_react_stranger_cannot(self, alice, bob, carol):
        r = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "hello react"})
        assert r.status_code == 200
        msg = r.json()
        mid = msg["msg_id"]
        # New message returns reactions=[]
        assert msg.get("reactions") == []
        # Sender reacts
        r1 = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": "🔥"})
        assert r1.status_code == 200, r1.text
        assert r1.json()["action"] == "added"
        # Recipient reacts with same emoji
        r2 = bob.post(f"{API}/messages/{mid}/reactions", json={"emoji": "🔥"})
        assert r2.status_code == 200
        # Aggregated GET → count=2
        r3 = bob.get(f"{API}/messages/{mid}/reactions")
        assert r3.status_code == 200
        reacts = r3.json()
        fire = [x for x in reacts if x["emoji"] == "🔥"][0]
        assert fire["count"] == 2
        assert fire["mine"] is True
        # Carol (stranger to thread) gets 403
        r4 = carol.post(f"{API}/messages/{mid}/reactions", json={"emoji": "❤️"})
        assert r4.status_code == 403
        # Alice toggles off
        r5 = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": "🔥"})
        assert r5.status_code == 200 and r5.json()["action"] == "removed"
        r6 = alice.get(f"{API}/messages/{mid}/reactions")
        fires = [x for x in r6.json() if x["emoji"] == "🔥"]
        if fires:
            assert fires[0]["count"] == 1
            assert fires[0]["mine"] is False

    def test_unverified_cannot_react(self, alice, bob):
        unv = _new_unverified("uv")
        r = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "hi 2"})
        mid = r.json()["msg_id"]
        r2 = unv.post(f"{API}/messages/{mid}/reactions", json={"emoji": "👍"})
        assert r2.status_code == 403

    def test_dm_messages_include_reactions_field(self, alice, bob):
        # Send a message and ensure GET returns it with a reactions list (with the emoji we add)
        r = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "with reaction"})
        mid = r.json()["msg_id"]
        bob.post(f"{API}/messages/{mid}/reactions", json={"emoji": "❤️"})
        r2 = alice.get(f"{API}/chat/dm/{bob._uid}", params={"limit": 50})
        assert r2.status_code == 200
        msgs = r2.json()
        target = next((m for m in msgs if m["msg_id"] == mid), None)
        assert target is not None
        assert isinstance(target.get("reactions"), list)
        assert any(x["emoji"] == "❤️" for x in target["reactions"])


# ---------------------------------------------------------------------------
# 3. Community message reactions
# ---------------------------------------------------------------------------
class TestCommunityReactions:
    def test_member_can_react_non_member_cannot(self, mdb, alice):
        # alice creates a community, bob joins, carol does not
        bob = _new_verified(mdb, "bobc")
        carol = _new_verified(mdb, "carolc")
        r = alice.post(f"{API}/communities", json={"name": f"TEST_i7 com {uuid.uuid4().hex[:6]}", "description": "x"})
        assert r.status_code == 200
        cid = r.json()["community_id"]
        bob.post(f"{API}/communities/{cid}/join")
        # Alice posts a message
        rm = alice.post(f"{API}/communities/{cid}/messages", json={"content": "olá comunidade"})
        assert rm.status_code == 200
        assert rm.json().get("reactions") == []
        mid = rm.json()["msg_id"]
        # bob (member) reacts
        rb = bob.post(f"{API}/messages/{mid}/reactions", json={"emoji": "🎮"})
        assert rb.status_code == 200
        # carol (non-member) 403
        rc = carol.post(f"{API}/messages/{mid}/reactions", json={"emoji": "👍"})
        assert rc.status_code == 403


# ---------------------------------------------------------------------------
# 4. Review reactions / likes / comments
# ---------------------------------------------------------------------------
class TestReviewReactionsLikesComments:
    @pytest.fixture(scope="class")
    def review(self, alice):
        gid = _any_game_id()
        rv = _post_review(alice, gid, rating=9, note="Review for reactions TEST_i7.")
        return rv

    def test_toggle_react_and_public_get(self, alice, review):
        rid = review["review_id"]
        r1 = alice.post(f"{API}/reviews/{rid}/reactions", json={"emoji": "🔥"})
        assert r1.status_code == 200
        assert r1.json()["action"] == "added"
        # Public GET (no auth)
        r2 = requests.get(f"{API}/reviews/{rid}/reactions")
        assert r2.status_code == 200
        reacts = r2.json()
        fire = [x for x in reacts if x["emoji"] == "🔥"][0]
        assert fire["count"] >= 1
        assert fire["mine"] is False  # unauthenticated
        # Authenticated GET (alice) → mine=True
        r3 = alice.get(f"{API}/reviews/{rid}/reactions")
        fire2 = [x for x in r3.json() if x["emoji"] == "🔥"][0]
        assert fire2["mine"] is True
        # Toggle off
        r4 = alice.post(f"{API}/reviews/{rid}/reactions", json={"emoji": "🔥"})
        assert r4.json()["action"] == "removed"

    def test_toggle_like(self, alice, review):
        rid = review["review_id"]
        r1 = alice.post(f"{API}/reviews/{rid}/like")
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["action"] in ("liked", "unliked")
        assert "count" in body1 and "mine" in body1
        # Toggle
        r2 = alice.post(f"{API}/reviews/{rid}/like")
        assert r2.status_code == 200
        assert r2.json()["action"] != body1["action"]

    def test_unverified_cannot_like_or_react_or_comment(self, review):
        rid = review["review_id"]
        unv = _new_unverified("uv2")
        assert unv.post(f"{API}/reviews/{rid}/like").status_code == 403
        assert unv.post(f"{API}/reviews/{rid}/reactions", json={"emoji": "👍"}).status_code == 403
        assert unv.post(f"{API}/reviews/{rid}/comments", json={"content": "x"}).status_code == 403

    def test_comments_post_list_delete(self, alice, admin_session, mdb, review):
        rid = review["review_id"]
        # Empty initial list ok (or has prior comments)
        r0 = requests.get(f"{API}/reviews/{rid}/comments")
        assert r0.status_code == 200
        before_count = len(r0.json())
        # Post comment by alice
        r1 = alice.post(f"{API}/reviews/{rid}/comments", json={"content": "Boa review!"})
        assert r1.status_code == 200, r1.text
        c1 = r1.json()
        cid1 = c1["comment_id"]
        assert c1["content"] == "Boa review!"
        # Post second by another user
        bob = _new_verified(mdb, "bobcm")
        r2 = bob.post(f"{API}/reviews/{rid}/comments", json={"content": "concordo"})
        assert r2.status_code == 200
        cid2 = r2.json()["comment_id"]
        # List is public and ascending
        r3 = requests.get(f"{API}/reviews/{rid}/comments")
        assert r3.status_code == 200
        listed = r3.json()
        assert len(listed) >= before_count + 2
        # Ascending order
        times = [c["created_at"] for c in listed]
        assert times == sorted(times)
        # Bob cannot delete alice's comment
        rdel = bob.delete(f"{API}/reviews/comments/{cid1}")
        assert rdel.status_code == 403
        # Alice can delete own
        assert alice.delete(f"{API}/reviews/comments/{cid1}").status_code == 200
        # Admin can delete bob's
        assert admin_session.delete(f"{API}/reviews/comments/{cid2}").status_code == 200


# ---------------------------------------------------------------------------
# 5. Pagination with `before`
# ---------------------------------------------------------------------------
class TestPagination:
    def test_dm_before(self, mdb):
        a = _new_verified(mdb, "pa")
        b = _new_verified(mdb, "pb")
        _be_friends(a, b)
        # Post 5 messages
        mids = []
        for i in range(5):
            r = a.post(f"{API}/chat/dm/{b._uid}", json={"content": f"m{i}"})
            mids.append(r.json())
        # Get first batch with limit=3 → last 3 messages (server returns ascending by created_at after sort)
        r = a.get(f"{API}/chat/dm/{b._uid}", params={"limit": 3})
        assert r.status_code == 200
        batch1 = r.json()
        assert len(batch1) == 3
        # Use earliest created_at as `before` cursor
        oldest_ts = batch1[0]["created_at"]
        r2 = a.get(f"{API}/chat/dm/{b._uid}", params={"limit": 3, "before": oldest_ts})
        assert r2.status_code == 200
        batch2 = r2.json()
        # All returned messages must be strictly older than oldest_ts
        for m in batch2:
            assert m["created_at"] < oldest_ts

    def test_community_before(self, mdb):
        owner = _new_verified(mdb, "pcom")
        r = owner.post(f"{API}/communities", json={"name": f"TEST_i7 pag {uuid.uuid4().hex[:6]}", "description": "x"})
        cid = r.json()["community_id"]
        for i in range(4):
            owner.post(f"{API}/communities/{cid}/messages", json={"content": f"msg{i}"})
        r1 = owner.get(f"{API}/communities/{cid}/messages", params={"limit": 2})
        assert r1.status_code == 200
        b1 = r1.json()
        assert len(b1) == 2
        oldest_ts = b1[0]["created_at"]
        r2 = owner.get(f"{API}/communities/{cid}/messages", params={"limit": 5, "before": oldest_ts})
        assert r2.status_code == 200
        for m in r2.json():
            assert m["created_at"] < oldest_ts


# ---------------------------------------------------------------------------
# 6. WebSocket
# ---------------------------------------------------------------------------
def _cookie_header(session: requests.Session) -> str:
    parts = []
    for c in session.cookies:
        parts.append(f"{c.name}={c.value}")
    return "; ".join(parts)


class TestWebSocket:
    @pytest.mark.asyncio
    async def test_ws_unauth_closes_4401(self):
        """No cookies → server should reject. Implementation rejects pre-accept via HTTP 403
        (Starlette behaviour when calling websocket.close() before accept). We accept either
        WebSocket close 4401 OR HTTP 403 handshake rejection."""
        url = f"{WS_BASE}/api/ws/chat/dm/anyuser"
        try:
            async with websockets.connect(url) as ws:
                await asyncio.wait_for(ws.recv(), timeout=5)
            assert False, "Expected handshake to fail without cookies"
        except wsexc.InvalidStatus as e:
            assert e.response.status_code in (401, 403)
        except wsexc.ConnectionClosed as e:
            assert e.rcvd is None or e.rcvd.code in (4401, 4403)

    @pytest.mark.asyncio
    async def test_ws_dm_not_friend_closes_4403(self, alice, mdb):
        """Stranger (logged in but not friend) tries to open DM ws with alice."""
        stranger = _new_verified(mdb, "ws_stranger")
        url = f"{WS_BASE}/api/ws/chat/dm/{alice._uid}"
        headers = [("Cookie", _cookie_header(stranger))]
        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
                await asyncio.wait_for(ws.recv(), timeout=5)
            assert False, "Expected handshake to fail when not friends"
        except wsexc.InvalidStatus as e:
            assert e.response.status_code in (401, 403)
        except wsexc.ConnectionClosed as e:
            assert e.rcvd is None or e.rcvd.code in (4401, 4403)

    @pytest.mark.asyncio
    async def test_ws_dm_ping_pong_and_broadcast(self, alice, bob):
        url = f"{WS_BASE}/api/ws/chat/dm/{alice._uid}"
        headers_bob = [("Cookie", _cookie_header(bob))]
        async with websockets.connect(url, additional_headers=headers_bob) as ws:
            await ws.send("ping")
            pong = await asyncio.wait_for(ws.recv(), timeout=5)
            assert pong == "pong"
            # Alice posts via HTTP -> bob (connected) should receive event
            await asyncio.sleep(0.2)
            r = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "ws-broadcast"})
            assert r.status_code == 200
            payload = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(payload)
            assert data.get("event") == "new_message"
            assert data["message"]["content"] == "ws-broadcast"
            assert "reactions" in data["message"]

    @pytest.mark.asyncio
    async def test_ws_community_non_member_4403_and_broadcast(self, mdb):
        owner = _new_verified(mdb, "wso")
        member = _new_verified(mdb, "wsm")
        outsider = _new_verified(mdb, "wsx")
        r = owner.post(f"{API}/communities", json={"name": f"TEST_i7 ws {uuid.uuid4().hex[:6]}", "description": "x"})
        cid = r.json()["community_id"]
        member.post(f"{API}/communities/{cid}/join")
        url = f"{WS_BASE}/api/ws/chat/community/{cid}"
        # Outsider rejected (HTTP 403 handshake or close 4403)
        try:
            async with websockets.connect(url, additional_headers=[("Cookie", _cookie_header(outsider))]) as ws:
                await asyncio.wait_for(ws.recv(), timeout=5)
            assert False, "Expected non-member to be rejected"
        except wsexc.InvalidStatus as e:
            assert e.response.status_code in (401, 403)
        except wsexc.ConnectionClosed as e:
            assert e.rcvd is None or e.rcvd.code in (4401, 4403)
        # Member receives broadcast when owner posts
        async with websockets.connect(url, additional_headers=[("Cookie", _cookie_header(member))]) as ws:
            await asyncio.sleep(0.2)
            r2 = owner.post(f"{API}/communities/{cid}/messages", json={"content": "hello ws com"})
            assert r2.status_code == 200
            data = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert data["event"] == "new_message"
            assert data["message"]["content"] == "hello ws com"


# ---------------------------------------------------------------------------
# 7. Quick regression of iter-6 essentials
# ---------------------------------------------------------------------------
class TestIter6Regression:
    def test_non_gmail_rejected(self):
        r = requests.post(f"{API}/auth/register", json={
            "email": f"nope_i7_{uuid.uuid4().hex[:6]}@yahoo.com",
            "password": "Password123!", "name": "Valid Name",
        })
        # Should be 400 with gmail message (422 happens only if other validation fails)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "gmail" in r.text.lower()

    def test_admin_login(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_games_top_bayesian(self):
        r = requests.get(f"{API}/games/top", params={"limit": 5})
        assert r.status_code == 200
        for g in r.json():
            assert "bayesian_score" in g
            assert "site_review_count" in g


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
