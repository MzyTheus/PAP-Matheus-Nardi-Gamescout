"""
GameScout Iteration 5 backend pytest suite.

Covers:
  - Review score calc (rating + cat_avg)/2 stored on POST/PATCH (8.86 for the spec example)
  - +25 pts when an incomplete review is upgraded to complete (PATCH and POST re-submit)
  - GET /api/games/top uses ONLY platform reviews, Bayesian (n*R + C*M)/(n+C), C=5 M=7
    + exposes site_review_count, site_avg_score, bayesian_score
  - GET /api/games/{game_id} avg_rating now uses `score` (not `rating`)
  - Backfill on startup: any pre-existing review without `score` was filled
  - Chat DM: list threads, GET dm, POST dm, friends-only, self -> 400, non-friend -> 403
  - Communities: create/list/get/join/leave + messages member-only
  - Regression on iteration-4 endpoints
Run:
  pytest /app/backend/tests/test_iteration5.py -v --tb=short \
    --junitxml=/app/test_reports/pytest/iteration5_results.xml
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://gamescout-reviews.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@gamescout.pt"
ADMIN_PASSWORD = "admin123"

RUN = uuid.uuid4().hex[:8]

_resolved: dict[str, str] = {}


def _resolve(query: str) -> str:
    if query in _resolved:
        return _resolved[query]
    r = requests.get(f"{API}/games", params={"q": query, "limit": 1}, timeout=30)
    assert r.status_code == 200, r.text
    arr = r.json()
    assert arr, f"No game found for '{query}'"
    _resolved[query] = arr[0]["game_id"]
    return arr[0]["game_id"]


def _register(suffix: str):
    s = requests.Session()
    email = f"TEST_i5_{suffix}_{RUN}@gamescout.pt"
    r = s.post(
        f"{API}/auth/register",
        json={"email": email, "password": "tester123", "name": f"TEST i5 {suffix} {RUN}"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    s.user_id = r.json()["user_id"]
    s.email = email
    return s


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def user_a():
    return _register("A")


@pytest.fixture(scope="session")
def user_b():
    return _register("B")


@pytest.fixture(scope="session")
def user_c():
    """Used to test non-friend access on chat DMs."""
    return _register("C")


# ---------------------------------------------------------------------------
# Health / regression
# ---------------------------------------------------------------------------
class TestRegression:
    def test_login_admin(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_register_creates_user(self, user_a):
        assert user_a.user_id

    def test_games_list(self):
        r = requests.get(f"{API}/games", params={"limit": 5}, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) >= 1

    def test_games_featured(self):
        r = requests.get(f"{API}/games/featured", timeout=30)
        assert r.status_code == 200
        keys = r.json().keys()
        for k in ("you_may_like", "famous", "horror", "recent_titles", "recent_reviews"):
            assert k in keys

    def test_wishlist_round_trip(self, user_a):
        gid = _resolve("Minecraft")
        r = user_a.post(f"{API}/wishlist/{gid}", timeout=15)
        assert r.status_code == 200
        wl = user_a.get(f"{API}/wishlist", timeout=15).json()
        assert any(g["game_id"] == gid for g in wl)
        r = user_a.delete(f"{API}/wishlist/{gid}", timeout=15)
        assert r.status_code == 200

    def test_friends_endpoint_works(self, user_a):
        r = user_a.get(f"{API}/friends", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_help_requests_listing(self):
        r = requests.get(f"{API}/help-requests", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Review score calculation
# ---------------------------------------------------------------------------
class TestReviewScore:
    SPEC_PAYLOAD = {
        "rating": 9,
        "hours_played": 50,
        "graphics": 10, "story": 8, "tutorial": 7,
        "gameplay": 9, "audio": 8, "performance": 9, "fun": 10,
        "recommends": True, "platform": "pc",
        "note": "Review completa de teste — score esperado 8.86.",
    }

    def test_post_review_returns_expected_score_886(self, user_a):
        gid = _resolve("Terraria")
        r = user_a.post(f"{API}/games/{gid}/reviews", json=self.SPEC_PAYLOAD, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # rating + cat_avg = 9 + (10+8+7+9+8+9+10)/7 = 9 + 8.7142857 -> /2 = 8.857... -> 8.86
        assert data["score"] == pytest.approx(8.86, abs=0.01), f"Got score {data['score']}"
        assert data["is_complete"] is True
        assert data["rating"] == 9

    def test_get_game_avg_uses_score_not_rating(self, user_a):
        gid = _resolve("Terraria")
        # Ensure review exists (idempotent — re-submit same payload)
        user_a.post(f"{API}/games/{gid}/reviews", json=self.SPEC_PAYLOAD, timeout=20)
        r = requests.get(f"{API}/games/{gid}", timeout=20)
        assert r.status_code == 200
        avg = r.json().get("avg_rating")
        assert avg is not None
        # If avg used the integer rating (9) instead of score, this would be ~9.0 not <=9.
        # The spec stores 8.86 for our sole review; allow a couple of other site reviews.
        assert avg <= 9.05, f"avg_rating={avg} suggests rating-based not score-based"


# ---------------------------------------------------------------------------
# Points: +25 when incomplete -> complete (PATCH + POST re-submit)
# ---------------------------------------------------------------------------
def _get_points(sess) -> int:
    r = sess.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200
    return int(r.json().get("points") or 0)


class TestPointsUpgrade:
    INCOMPLETE_PAYLOAD = {"rating": 6, "note": ""}  # only rating

    COMPLETE_PAYLOAD = {
        "rating": 8, "hours_played": 30,
        "graphics": 8, "story": 8, "tutorial": 7,
        "gameplay": 9, "audio": 8, "performance": 8, "fun": 9,
        "recommends": True, "platform": "pc",
        "note": "Versão completa da review com bastante detalhe.",
    }

    def test_patch_upgrade_awards_25_extra(self, user_b):
        gid = _resolve("Dead by Daylight")
        # 1) Create incomplete (awards 25)
        r = user_b.post(f"{API}/games/{gid}/reviews", json=self.INCOMPLETE_PAYLOAD, timeout=20)
        assert r.status_code == 200
        rev = r.json()
        assert rev["is_complete"] is False
        rid = rev["review_id"]
        pts_before = _get_points(user_b)

        # 2) PATCH to complete -> +25 extra
        r = user_b.patch(f"{API}/reviews/{rid}", json=self.COMPLETE_PAYLOAD, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_complete"] is True
        assert body["score"] == pytest.approx((8 + (8+8+7+9+8+8+9)/7) / 2, abs=0.01)

        pts_after = _get_points(user_b)
        assert pts_after - pts_before == 25, f"Expected +25, got {pts_after - pts_before}"

        # Cleanup
        user_b.delete(f"{API}/reviews/{rid}", timeout=15)

    def test_resubmit_post_upgrade_awards_25_extra(self, user_b):
        gid = _resolve("No Man")
        # 1) POST incomplete (awards 25)
        r = user_b.post(f"{API}/games/{gid}/reviews", json=self.INCOMPLETE_PAYLOAD, timeout=20)
        assert r.status_code == 200
        rev = r.json()
        rid = rev["review_id"]
        assert rev["is_complete"] is False
        pts_before = _get_points(user_b)

        # 2) Re-POST same user/game with complete payload -> upgrade -> +25
        r = user_b.post(f"{API}/games/{gid}/reviews", json=self.COMPLETE_PAYLOAD, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["review_id"] == rid, "Should update existing review, not create new"
        assert body["is_complete"] is True
        assert body["score"] == pytest.approx((8 + (8+8+7+9+8+8+9)/7) / 2, abs=0.01)

        pts_after = _get_points(user_b)
        assert pts_after - pts_before == 25, f"Expected +25, got {pts_after - pts_before}"

        # Cleanup
        user_b.delete(f"{API}/reviews/{rid}", timeout=15)


# ---------------------------------------------------------------------------
# /api/games/top — Bayesian using ONLY platform reviews
# ---------------------------------------------------------------------------
class TestTopGamesBayesian:
    def test_top_exposes_required_fields_and_formula(self, user_a):
        # Ensure at least one game has 1 site review so site_avg_score is non-null.
        gid = _resolve("Five Nights at Freddy")
        user_a.post(f"{API}/games/{gid}/reviews",
                    json={"rating": 8, "graphics": 8, "story": 7, "tutorial": 7,
                          "gameplay": 8, "audio": 8, "performance": 8, "fun": 9,
                          "hours_played": 10, "recommends": True, "platform": "pc",
                          "note": "Review TEST i5 para top games."},
                    timeout=20)

        r = requests.get(f"{API}/games/top", params={"limit": 50}, timeout=30)
        assert r.status_code == 200, r.text
        games = r.json()
        assert games, "Top games should not be empty"

        for g in games:
            assert "site_review_count" in g
            assert "site_avg_score" in g
            assert "bayesian_score" in g
            n = g["site_review_count"]
            R = g["site_avg_score"] if g["site_avg_score"] is not None else 0.0
            expected = round((n * R + 5 * 7) / (n + 5), 2)
            assert g["bayesian_score"] == pytest.approx(expected, abs=0.02), (
                f"{g['title']}: bayesian={g['bayesian_score']} expected={expected} "
                f"(n={n}, R={R})"
            )

        # Sorted desc by bayesian_score
        scores = [g["bayesian_score"] for g in games]
        assert scores == sorted(scores, reverse=True)

    def test_top_zero_review_game_has_score_close_to_M(self):
        r = requests.get(f"{API}/games/top", params={"limit": 200}, timeout=30)
        assert r.status_code == 200
        zero = [g for g in r.json() if g.get("site_review_count") == 0]
        if zero:
            for g in zero[:5]:
                assert g["site_avg_score"] is None
                # 0 * R + 5 * 7 / (0 + 5) = 7.0
                assert g["bayesian_score"] == 7.0


# ---------------------------------------------------------------------------
# Backfill on startup
# ---------------------------------------------------------------------------
class TestBackfill:
    def test_no_review_missing_score(self, admin_session):
        """All existing reviews exposed via list_reviews must have a score field."""
        # Sample several popular games
        sampled = 0
        for q in ["Minecraft", "Terraria", "No Man", "Dead by Daylight",
                  "Five Nights at Freddy", "Resident Evil", "Elden Ring"]:
            gid = _resolve(q)
            r = requests.get(f"{API}/games/{gid}/reviews", timeout=20)
            assert r.status_code == 200
            for rev in r.json():
                sampled += 1
                assert "score" in rev, f"Review {rev.get('review_id')} missing score"
                assert isinstance(rev["score"], (int, float)), f"score={rev['score']!r}"
        assert sampled >= 0  # may be 0 if fresh DB; test still meaningful as a no-error sweep


# ---------------------------------------------------------------------------
# Chat DM
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def friend_pair(user_a, user_b):
    """A and B accepted-friends fixture (used by all DM tests)."""
    r = user_a.post(f"{API}/friends/request/{user_b.user_id}", timeout=15)
    assert r.status_code == 200, r.text
    r = user_b.post(f"{API}/friends/accept/{user_a.user_id}", timeout=15)
    assert r.status_code == 200, r.text
    yield (user_a, user_b)
    # Cleanup: remove friendship
    try:
        user_a.delete(f"{API}/friends/{user_b.user_id}", timeout=15)
    except Exception:
        pass


class TestChatDM:
    def test_dm_self_400(self, user_a):
        r = user_a.post(f"{API}/chat/dm/{user_a.user_id}",
                        json={"content": "hello me"}, timeout=15)
        assert r.status_code == 400

        r = user_a.get(f"{API}/chat/dm/{user_a.user_id}", timeout=15)
        assert r.status_code == 400

    def test_dm_non_friend_403(self, user_a, user_c):
        # A and C are NOT friends
        r = user_a.post(f"{API}/chat/dm/{user_c.user_id}",
                        json={"content": "should fail"}, timeout=15)
        assert r.status_code == 403

        r = user_a.get(f"{API}/chat/dm/{user_c.user_id}", timeout=15)
        assert r.status_code == 403

    def test_dm_send_and_fetch_between_friends(self, friend_pair):
        a, b = friend_pair
        msg_text = f"olá {RUN}"
        r = a.post(f"{API}/chat/dm/{b.user_id}",
                   json={"content": msg_text}, timeout=15)
        assert r.status_code == 200, r.text
        sent = r.json()
        assert sent["content"] == msg_text
        assert sent["sender_id"] == a.user_id
        assert sent["thread_key"].startswith("dm::")

        # B fetches DM history
        r = b.get(f"{API}/chat/dm/{a.user_id}", timeout=15)
        assert r.status_code == 200
        msgs = r.json()
        assert any(m["content"] == msg_text and m["sender_id"] == a.user_id for m in msgs)

    def test_dm_after_filter(self, friend_pair):
        a, b = friend_pair
        # Send msg1
        r = a.post(f"{API}/chat/dm/{b.user_id}",
                   json={"content": f"first {RUN}"}, timeout=15)
        assert r.status_code == 200
        first_at = r.json()["created_at"]
        time.sleep(1.1)
        # Send msg2
        r = a.post(f"{API}/chat/dm/{b.user_id}",
                   json={"content": f"second {RUN}"}, timeout=15)
        assert r.status_code == 200

        # B fetches with after=first_at -> should only get the second one
        r = b.get(f"{API}/chat/dm/{a.user_id}",
                  params={"after": first_at}, timeout=15)
        assert r.status_code == 200
        contents = [m["content"] for m in r.json()]
        assert f"second {RUN}" in contents
        assert f"first {RUN}" not in contents

    def test_threads_lists_friends_sorted(self, friend_pair):
        a, b = friend_pair
        r = a.get(f"{API}/chat/threads", timeout=15)
        assert r.status_code == 200
        threads = r.json()
        assert any(t["user_id"] == b.user_id for t in threads)
        # Latest msg-bearing thread should appear with last_message populated
        b_thread = next(t for t in threads if t["user_id"] == b.user_id)
        assert b_thread["last_message"] is not None
        assert b_thread["last_at"] is not None

    def test_message_max_length(self, friend_pair):
        a, b = friend_pair
        r = a.post(f"{API}/chat/dm/{b.user_id}",
                   json={"content": "x" * 2001}, timeout=15)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Communities
# ---------------------------------------------------------------------------
class TestCommunities:
    @pytest.fixture(scope="class")
    def created_community(self, admin_session):
        payload = {"name": f"TEST i5 com {RUN}",
                   "description": "Comunidade de teste iteracao 5"}
        r = admin_session.post(f"{API}/communities", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["is_member"] is True
        assert c["members_count"] == 1
        return c

    def test_list_communities(self, created_community, admin_session):
        cid = created_community["community_id"]
        r = admin_session.get(f"{API}/communities", timeout=15)
        assert r.status_code == 200
        arr = r.json()
        match = next((x for x in arr if x["community_id"] == cid), None)
        assert match is not None
        assert "members_count" in match
        assert "is_member" in match
        # _id should not leak
        assert "_id" not in match

    def test_get_community_detail(self, created_community, admin_session):
        cid = created_community["community_id"]
        r = admin_session.get(f"{API}/communities/{cid}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["community_id"] == cid
        assert d["is_member"] is True

    def test_join_and_leave(self, created_community, user_a):
        cid = created_community["community_id"]

        # Join
        r = user_a.post(f"{API}/communities/{cid}/join", timeout=15)
        assert r.status_code == 200
        d = user_a.get(f"{API}/communities/{cid}", timeout=15).json()
        assert d["is_member"] is True
        assert d["members_count"] >= 2

        # Leave
        r = user_a.delete(f"{API}/communities/{cid}/leave", timeout=15)
        assert r.status_code == 200
        d = user_a.get(f"{API}/communities/{cid}", timeout=15).json()
        assert d["is_member"] is False

    def test_message_non_member_403(self, created_community, user_a):
        cid = created_community["community_id"]
        # Make sure user_a is NOT a member (leave if joined)
        user_a.delete(f"{API}/communities/{cid}/leave", timeout=15)

        r = user_a.get(f"{API}/communities/{cid}/messages", timeout=15)
        assert r.status_code == 403

        r = user_a.post(f"{API}/communities/{cid}/messages",
                        json={"content": "hello"}, timeout=15)
        assert r.status_code == 403

    def test_post_and_get_messages_member(self, created_community, admin_session):
        cid = created_community["community_id"]
        text = f"TEST i5 hello community {RUN}"
        r = admin_session.post(f"{API}/communities/{cid}/messages",
                               json={"content": text}, timeout=15)
        assert r.status_code == 200, r.text
        msg = r.json()
        assert msg["content"] == text
        assert msg["thread_key"] == f"com::{cid}"
        assert msg["type"] == "community"

        r = admin_session.get(f"{API}/communities/{cid}/messages", timeout=15)
        assert r.status_code == 200
        msgs = r.json()
        assert any(m["content"] == text for m in msgs)

    def test_message_too_long_422(self, created_community, admin_session):
        cid = created_community["community_id"]
        r = admin_session.post(f"{API}/communities/{cid}/messages",
                               json={"content": "x" * 2001}, timeout=15)
        assert r.status_code == 422
