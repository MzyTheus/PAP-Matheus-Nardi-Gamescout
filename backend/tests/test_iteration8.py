"""GameScout backend tests — Iteration 8.

Coverage:
- Like verb standardisation: POST /api/reviews/{id}/like returns action='added' / 'removed'.
- Reaction verbs: also action='added' / 'removed' (consistent).
- Emoji validation: POST .../reactions with emoji NOT in catalog returns 400 with
  message 'Emoji não está no catálogo. Pede ao admin para adicionar.'
- Default emojis (👌❤️🤣😊😁👍🔥😢🎮) always accepted.
- Admin add custom emoji → immediately valid for reactions; delete → rejected again.
- Lifespan: no deprecation, admin promoted, /api/emojis responds.
- Refactor: routes moved to routers/social.py still functional.
- Regression: chat/dm returns `reactions` field hydrated via _social_helpers.
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gamescout-reviews.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "matheusvittore670@gmail.com"
ADMIN_PASSWORD = "admin123"

REVIEW_CATEGORIES = ["graphics", "story", "tutorial", "gameplay", "audio", "performance", "fun"]
DEFAULT_EMOJIS = ["👌", "❤️", "🤣", "😊", "😁", "👍", "🔥", "😢", "🎮"]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mdb():
    return MongoClient(MONGO_URL)[DB_NAME]


def _gmail(prefix="i8user"):
    return f"{prefix}_i8_{uuid.uuid4().hex[:8]}@gmail.com"


def _register_verified(mdb, prefix="user"):
    s = requests.Session()
    email = _gmail(prefix)
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "Password123!", "name": "I8 User"})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    uid = s.get(f"{API}/auth/me").json()["user_id"]
    rec = mdb.email_verifications.find_one({"user_id": uid})
    assert rec, "no verification code"
    rv = s.post(f"{API}/auth/verify-email", json={"code": rec["code"]})
    assert rv.status_code == 200, rv.text
    s._uid = uid
    s._email = email
    return s


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json().get("role") == "admin"
    return s


@pytest.fixture(scope="session")
def alice(mdb):
    return _register_verified(mdb, "alice8")


@pytest.fixture(scope="session")
def bob(mdb, alice):
    b = _register_verified(mdb, "bob8")
    r = alice.post(f"{API}/friends/request/{b._uid}")
    assert r.status_code == 200, r.text
    r2 = b.post(f"{API}/friends/accept/{alice._uid}")
    assert r2.status_code == 200, r2.text
    return b


@pytest.fixture(scope="session")
def review(alice):
    gid = requests.get(f"{API}/games", params={"limit": 1}).json()[0]["game_id"]
    payload = {
        "rating": 8, "hours_played": 10, "recommends": True,
        "platform": "pc", "note": "iter8 review",
        **{c: 8 for c in REVIEW_CATEGORIES},
    }
    r = alice.post(f"{API}/games/{gid}/reviews", json=payload)
    if r.status_code in (400, 409):
        existing = requests.get(f"{API}/games/{gid}/reviews").json()
        for rv in existing:
            if rv.get("user_id") == alice._uid:
                return rv
        pytest.skip("Could not create or find existing review")
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Lifespan / startup
# ---------------------------------------------------------------------------
class TestLifespanStartup:
    def test_emojis_endpoint_alive(self):
        r = requests.get(f"{API}/emojis")
        assert r.status_code == 200
        body = r.json()
        for e in DEFAULT_EMOJIS:
            assert e in body["basic"], f"default {e} missing"

    def test_admin_user_promoted(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json().get("role") == "admin"


# ---------------------------------------------------------------------------
# 2. Like verb standardisation — action='added' / 'removed'
# ---------------------------------------------------------------------------
class TestLikeVerbs:
    def test_like_returns_added_then_removed(self, alice, review):
        rid = review["review_id"]
        # Ensure clean state — toggle twice if liked
        first = alice.post(f"{API}/reviews/{rid}/like")
        assert first.status_code == 200, first.text
        body1 = first.json()
        assert body1["action"] in ("added", "removed"), f"got {body1['action']}"
        # The verbs MUST NOT be the legacy ones
        assert body1["action"] not in ("liked", "unliked"), "Legacy verb still returned!"
        assert "count" in body1 and "mine" in body1

        second = alice.post(f"{API}/reviews/{rid}/like")
        assert second.status_code == 200
        body2 = second.json()
        assert body2["action"] in ("added", "removed")
        assert body2["action"] != body1["action"], "action should toggle"
        assert body2["action"] not in ("liked", "unliked")


# ---------------------------------------------------------------------------
# 3. Reaction verb consistency (added/removed) — review and message
# ---------------------------------------------------------------------------
class TestReactionVerbs:
    def test_review_reaction_added_removed(self, alice, review):
        rid = review["review_id"]
        r1 = alice.post(f"{API}/reviews/{rid}/reactions", json={"emoji": "👍"})
        assert r1.status_code == 200, r1.text
        a1 = r1.json()["action"]
        assert a1 in ("added", "removed")
        r2 = alice.post(f"{API}/reviews/{rid}/reactions", json={"emoji": "👍"})
        assert r2.status_code == 200
        a2 = r2.json()["action"]
        assert a2 in ("added", "removed")
        assert a1 != a2

    def test_dm_message_reaction_added_removed(self, alice, bob):
        m = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "i8 reactverb"})
        assert m.status_code == 200, m.text
        mid = m.json()["msg_id"]
        r1 = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": "🔥"})
        assert r1.status_code == 200
        assert r1.json()["action"] == "added"
        r2 = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": "🔥"})
        assert r2.status_code == 200
        assert r2.json()["action"] == "removed"


# ---------------------------------------------------------------------------
# 4. Emoji validation against catalog
# ---------------------------------------------------------------------------
class TestEmojiValidation:
    def test_default_emojis_accepted_on_message(self, alice, bob):
        m = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "i8 validation"})
        mid = m.json()["msg_id"]
        for e in DEFAULT_EMOJIS:
            r = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": e})
            assert r.status_code == 200, f"default emoji {e} rejected: {r.status_code} {r.text}"
            # toggle back off so we don't leave them all attached
            alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": e})

    def test_invalid_emoji_rejected_on_message(self, alice, bob):
        m = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "i8 invalid"})
        mid = m.json()["msg_id"]
        for bad in ["XYZ", "ABCD", "qualquer", "lol", "z"]:
            r = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": bad})
            assert r.status_code == 400, f"emoji '{bad}' should be 400, got {r.status_code}: {r.text}"
            assert "catálogo" in r.text or "catalogo" in r.text.lower(), f"missing catálogo message: {r.text}"

    def test_invalid_emoji_rejected_on_review(self, alice, review):
        rid = review["review_id"]
        for bad in ["XYZ", "foo", "barbaz"]:
            r = alice.post(f"{API}/reviews/{rid}/reactions", json={"emoji": bad})
            assert r.status_code == 400, f"review emoji '{bad}' should be 400, got {r.status_code}: {r.text}"
            assert "catálogo" in r.text or "catalogo" in r.text.lower()


# ---------------------------------------------------------------------------
# 5. Custom emoji round-trip: add → accepted; remove → rejected
# ---------------------------------------------------------------------------
class TestCustomEmojiRoundTrip:
    def test_admin_add_then_react_then_remove(self, admin_session, alice, bob):
        # Pick a custom emoji unlikely to be in defaults
        custom = "🦄"
        # Cleanup any pre-existing
        existing = requests.get(f"{API}/emojis").json().get("custom", [])
        for e in existing:
            if e["emoji"] == custom:
                admin_session.delete(f"{API}/admin/emojis/{e['emoji_id']}")

        # 1) Before adding → must be rejected
        m = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "i8 custom test"})
        mid = m.json()["msg_id"]
        r_before = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": custom})
        assert r_before.status_code == 400, f"before add: expected 400, got {r_before.status_code}"

        # 2) Admin adds the custom emoji
        ra = admin_session.post(f"{API}/admin/emojis", json={"emoji": custom, "name": "unicorn"})
        assert ra.status_code == 200, ra.text
        eid = ra.json()["emoji_id"]

        # 3) Now it should be valid immediately (no restart)
        r_after = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": custom})
        assert r_after.status_code == 200, f"after add: expected 200, got {r_after.status_code} {r_after.text}"
        assert r_after.json()["action"] == "added"

        # 4) Admin removes the emoji
        rd = admin_session.delete(f"{API}/admin/emojis/{eid}")
        assert rd.status_code == 200, rd.text

        # 5) Should be rejected again — try on a fresh message to avoid the toggle-removing-existing path
        m2 = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "i8 custom test post-del"})
        mid2 = m2.json()["msg_id"]
        r_post = alice.post(f"{API}/messages/{mid2}/reactions", json={"emoji": custom})
        assert r_post.status_code == 400, f"after delete: expected 400, got {r_post.status_code} {r_post.text}"


# ---------------------------------------------------------------------------
# 6. Refactor: social router endpoints still functional
# ---------------------------------------------------------------------------
class TestRefactorSmoke:
    def test_emojis_route(self):
        assert requests.get(f"{API}/emojis").status_code == 200

    def test_review_reactions_route(self, alice, review):
        rid = review["review_id"]
        r = alice.get(f"{API}/reviews/{rid}/reactions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_review_comments_route(self, alice, review):
        rid = review["review_id"]
        r = requests.get(f"{API}/reviews/{rid}/comments")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_dm_messages_include_reactions_hydration(self, alice, bob):
        """server.py uses _social_helpers['reactions_for_msgs'] to hydrate reactions on chat/dm GET."""
        m = alice.post(f"{API}/chat/dm/{bob._uid}", json={"content": "i8 hydrate"})
        mid = m.json()["msg_id"]
        # Add a reaction with a default emoji
        rr = alice.post(f"{API}/messages/{mid}/reactions", json={"emoji": "❤️"})
        assert rr.status_code == 200, rr.text
        # GET DM list and confirm reactions appear
        lst = alice.get(f"{API}/chat/dm/{bob._uid}", params={"limit": 50})
        assert lst.status_code == 200
        msgs = lst.json()
        target = next((mm for mm in msgs if mm["msg_id"] == mid), None)
        assert target is not None
        assert isinstance(target.get("reactions"), list)
        assert any(x["emoji"] == "❤️" for x in target["reactions"]), f"reactions: {target.get('reactions')}"


# ---------------------------------------------------------------------------
# 7. Regression — auth + top games
# ---------------------------------------------------------------------------
class TestRegression:
    def test_non_gmail_rejected(self):
        r = requests.post(f"{API}/auth/register", json={
            "email": f"x_i8_{uuid.uuid4().hex[:6]}@yahoo.com",
            "password": "Password123!", "name": "Valid Name",
        })
        assert r.status_code == 400
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
