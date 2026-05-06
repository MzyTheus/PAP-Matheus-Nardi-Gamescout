"""
GameScout backend pytest suite — covers auth, users, games, reviews, guides,
help requests, friends and ranking logic. Uses the external preview URL
(REACT_APP_BACKEND_URL) so cookies (secure/samesite=none) work correctly.

Run:
  pytest /app/backend/tests/backend_test.py -v --tb=short \
    --junitxml=/app/test_reports/pytest/pytest_results.xml
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gamescout-reviews.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@gamescout.pt"
ADMIN_PASSWORD = "admin123"

# Use unique suffix to avoid colliding with previous runs / brute-force lockout
RUN = uuid.uuid4().hex[:8]
TEST_USER_EMAIL = f"TEST_user_{RUN}@gamescout.pt"
TEST_USER_PASSWORD = "tester123"
TEST_USER_NAME = f"TEST User {RUN}"

SECOND_USER_EMAIL = f"TEST_second_{RUN}@gamescout.pt"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def admin_session():
    """Admin authenticated requests session (cookies)."""
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    assert "access_token" in s.cookies, "Admin session missing access_token cookie"
    return s


@pytest.fixture(scope="session")
def user_session():
    """Register + login a brand-new test user."""
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={
        "email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD, "name": TEST_USER_NAME,
    }, timeout=15)
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    data = r.json()
    s.user_id = data["user_id"]  # stash for later
    return s


@pytest.fixture(scope="session")
def second_user_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={
        "email": SECOND_USER_EMAIL, "password": TEST_USER_PASSWORD, "name": f"TEST Second {RUN}",
    }, timeout=15)
    assert r.status_code == 200, f"Second register failed: {r.status_code} {r.text}"
    s.user_id = r.json()["user_id"]
    return s


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------
class TestAuth:
    def test_register_returns_user_and_sets_cookies(self):
        s = requests.Session()
        email = f"TEST_reg_{uuid.uuid4().hex[:6]}@gamescout.pt"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "secret6", "name": "TEST Reg"
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Server lowercases emails on register — compare case-insensitively
        assert data["email"] == email.lower()
        assert data["name"] == "TEST Reg"
        assert data["user_id"].startswith("user_")
        assert data["points"] == 0
        assert data["role"] == "user"
        assert "password_hash" not in data
        assert "_id" not in data
        # Cookies
        assert "access_token" in s.cookies
        assert "refresh_token" in s.cookies

    def test_register_duplicate_email_returns_400(self, user_session):
        r = requests.post(f"{API}/auth/register", json={
            "email": TEST_USER_EMAIL, "password": "whatever", "name": "Dup"
        }, timeout=15)
        assert r.status_code == 400

    def test_login_admin_success(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        assert data["points"] == 10000
        assert "access_token" in s.cookies
        assert "refresh_token" in s.cookies

    def test_auth_me_with_cookie(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == ADMIN_EMAIL
        assert "password_hash" not in d

    def test_auth_me_no_cookie_returns_401(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_google_session_with_invalid_id_returns_401_or_502(self):
        r = requests.post(f"{API}/auth/google/session", json={"session_id": "invalid_session_xyz"}, timeout=20)
        assert r.status_code in (401, 502)


# ---------------------------------------------------------------------------
# Users & rank
# ---------------------------------------------------------------------------
class TestUsersAndRanks:
    def test_users_me_full_new_user_novato(self, user_session):
        r = user_session.get(f"{API}/users/me/full", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["points"] == 0
        assert d["rank"]["name"] == "Novato"
        assert d["rank"]["level"] == 1
        assert d["rank"]["next_name"] == "Explorador"
        assert d["rank"]["next_points"] == 50

    def test_users_me_full_admin_apreciador(self, admin_session):
        r = admin_session.get(f"{API}/users/me/full", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["points"] == 10000
        assert d["rank"]["name"] == "Apreciador de Obras"
        assert d["rank"]["level"] == 5
        assert d["rank"]["next_name"] is None

    def test_patch_users_me_updates_profile(self, user_session):
        payload = {
            "bio": "TEST bio",
            "social": {"discord": "tester#1234", "instagram": "tester_ig"},
            "prefs": {"favorite_game": "elden-ring", "platforms": ["pc", "ps5"], "pc_specs": "RTX 4070"},
        }
        r = user_session.patch(f"{API}/users/me", json=payload, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["bio"] == "TEST bio"
        assert d["social"]["discord"] == "tester#1234"
        assert d["prefs"]["favorite_game"] == "elden-ring"
        assert "pc" in d["prefs"]["platforms"]

        # Verify persistence via /auth/me
        r2 = user_session.get(f"{API}/auth/me", timeout=15)
        assert r2.json()["bio"] == "TEST bio"

    def test_users_search_excludes_self(self, user_session, second_user_session):
        r = user_session.get(f"{API}/users/search", params={"q": "TEST"}, timeout=15)
        assert r.status_code == 200
        ids = [u["user_id"] for u in r.json()]
        assert user_session.user_id not in ids
        # the second test user should appear
        assert any(u["user_id"] == second_user_session.user_id for u in r.json())


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------
class TestGames:
    def test_list_games_has_31(self):
        r = requests.get(f"{API}/games", params={"limit": 100}, timeout=15)
        assert r.status_code == 200
        games = r.json()
        assert len(games) >= 30, f"Expected ~31 games, got {len(games)}"
        # no _id leaked
        assert all("_id" not in g for g in games)
        assert all("game_id" in g and "title" in g for g in games)

    def test_list_games_search_q(self):
        r = requests.get(f"{API}/games", params={"q": "Zelda"}, timeout=15)
        assert r.status_code == 200
        titles = [g["title"].lower() for g in r.json()]
        assert any("zelda" in t for t in titles)

    def test_list_games_filter_genre(self):
        r = requests.get(f"{API}/games", params={"genre": "Terror"}, timeout=15)
        assert r.status_code == 200
        for g in r.json():
            assert "Terror" in g["genres"]

    def test_list_games_filter_platform(self):
        r = requests.get(f"{API}/games", params={"platform": "switch"}, timeout=15)
        assert r.status_code == 200
        for g in r.json():
            assert "switch" in g["platforms"]

    def test_featured_sections(self):
        r = requests.get(f"{API}/games/featured", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for key in ("you_may_like", "famous", "horror", "recent_titles", "recent_reviews"):
            assert key in d, f"missing section {key}"
        assert len(d["famous"]) > 0
        assert len(d["horror"]) > 0

    def test_get_game_detail_with_aggregates(self):
        r = requests.get(f"{API}/games/elden-ring", timeout=15)
        assert r.status_code == 200
        g = r.json()
        assert g["game_id"] == "elden-ring"
        assert "avg_rating" in g
        assert "review_count" in g

    def test_get_game_404(self):
        r = requests.get(f"{API}/games/does-not-exist", timeout=15)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Reviews + points
# ---------------------------------------------------------------------------
class TestReviews:
    def test_create_review_incomplete_awards_25(self, user_session):
        # Baseline points
        pts_before = user_session.get(f"{API}/users/me/full", timeout=15).json()["points"]

        payload = {"rating": 8, "note": "short"}  # missing many fields -> incomplete
        r = user_session.post(f"{API}/games/minecraft/reviews", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        rev = r.json()
        assert rev["rating"] == 8
        assert rev["is_complete"] is False
        assert rev["game_id"] == "minecraft"
        assert rev["user_id"] == user_session.user_id

        pts_after = user_session.get(f"{API}/users/me/full", timeout=15).json()["points"]
        assert pts_after - pts_before == 25, f"Expected +25 pts, got +{pts_after - pts_before}"

    def test_resubmit_review_updates_without_new_points(self, user_session):
        pts_before = user_session.get(f"{API}/users/me/full", timeout=15).json()["points"]
        # Upgrade to a COMPLETE review – should update, NOT re-award points
        payload = {
            "rating": 9, "hours_played": 120, "graphics": 9, "story": 8,
            "tutorial": 7, "gameplay": 10, "recommends": True, "platform": "pc",
            "note": "Jogo fantástico com inúmeras possibilidades criativas."
        }
        r = user_session.post(f"{API}/games/minecraft/reviews", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        rev = r.json()
        assert rev["rating"] == 9
        assert rev["is_complete"] is True

        pts_after = user_session.get(f"{API}/users/me/full", timeout=15).json()["points"]
        assert pts_after == pts_before, "Re-submission should NOT award additional points"

    def test_create_complete_review_awards_50(self, user_session):
        pts_before = user_session.get(f"{API}/users/me/full", timeout=15).json()["points"]
        payload = {
            "rating": 10, "hours_played": 80, "graphics": 10, "story": 10,
            "tutorial": 9, "gameplay": 10, "recommends": True, "platform": "pc",
            "note": "Obra-prima absoluta da FromSoftware."
        }
        r = user_session.post(f"{API}/games/elden-ring/reviews", json=payload, timeout=15)
        assert r.status_code == 200
        assert r.json()["is_complete"] is True
        pts_after = user_session.get(f"{API}/users/me/full", timeout=15).json()["points"]
        assert pts_after - pts_before == 50

    def test_list_reviews_for_game(self, user_session):
        r = requests.get(f"{API}/games/minecraft/reviews", timeout=15)
        assert r.status_code == 200
        reviews = r.json()
        assert any(rv["user_id"] == user_session.user_id for rv in reviews)

    def test_game_detail_aggregates_updated(self):
        r = requests.get(f"{API}/games/elden-ring", timeout=15)
        assert r.status_code == 200
        g = r.json()
        assert g["review_count"] >= 1
        assert g["avg_rating"] is not None


# ---------------------------------------------------------------------------
# Guides (Explorador+ gate)
# ---------------------------------------------------------------------------
class TestGuides:
    def test_guide_forbidden_for_low_points(self, second_user_session):
        # Brand-new user has 0 points → must be blocked
        payload = {"title": "Meu guia", "content": "Conteúdo bastante detalhado com passos.", "category": "dica"}
        r = second_user_session.post(f"{API}/games/elden-ring/guides", json=payload, timeout=15)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    def test_guide_created_by_admin(self, admin_session):
        payload = {"title": "TEST Guia Admin", "content": "Conteúdo longo suficiente para o guia.", "category": "tutorial"}
        r = admin_session.post(f"{API}/games/elden-ring/guides", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["title"] == "TEST Guia Admin"
        assert d["game_id"] == "elden-ring"
        assert d["author_name"] == "Admin"
        assert "_id" not in d

    def test_list_guides(self, admin_session):
        r = requests.get(f"{API}/games/elden-ring/guides", timeout=15)
        assert r.status_code == 200
        titles = [g["title"] for g in r.json()]
        assert any("TEST Guia Admin" == t for t in titles)


# ---------------------------------------------------------------------------
# Help requests
# ---------------------------------------------------------------------------
class TestHelp:
    def test_create_help_and_reply(self, user_session, admin_session):
        # Create
        payload = {"title": "TEST precisa de ajuda", "content": "Como derrotar o boss?", "kind": "ajuda", "game_id": "elden-ring"}
        r = user_session.post(f"{API}/help-requests", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        help_id = r.json()["help_id"]

        # List
        r2 = requests.get(f"{API}/help-requests", timeout=15)
        assert r2.status_code == 200
        assert any(h["help_id"] == help_id for h in r2.json())

        # Reply (admin)
        r3 = admin_session.post(f"{API}/help-requests/{help_id}/replies", json={"content": "Usa escudo!"}, timeout=15)
        assert r3.status_code == 200, r3.text
        assert r3.json()["content"] == "Usa escudo!"

        # Reply persists
        r4 = requests.get(f"{API}/help-requests", params={"game_id": "elden-ring"}, timeout=15)
        target = [h for h in r4.json() if h["help_id"] == help_id][0]
        assert len(target["replies"]) >= 1

    def test_create_help_unauth(self):
        r = requests.post(f"{API}/help-requests", json={"title": "x", "content": "y", "kind": "ajuda"}, timeout=15)
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------
class TestFriends:
    def test_send_request_accept_flow(self, user_session, second_user_session):
        # user -> second
        r = user_session.post(f"{API}/friends/request/{second_user_session.user_id}", timeout=15)
        assert r.status_code == 200, r.text

        # second should see pending
        r2 = second_user_session.get(f"{API}/friends/requests", timeout=15)
        assert r2.status_code == 200
        reqs = r2.json()
        assert any(rq["from_user"]["user_id"] == user_session.user_id for rq in reqs)

        # accept
        r3 = second_user_session.post(f"{API}/friends/accept/{user_session.user_id}", timeout=15)
        assert r3.status_code == 200

        # both sides see each other as friends
        f1 = user_session.get(f"{API}/friends", timeout=15).json()
        f2 = second_user_session.get(f"{API}/friends", timeout=15).json()
        assert any(f["user_id"] == second_user_session.user_id for f in f1)
        assert any(f["user_id"] == user_session.user_id for f in f2)

    def test_cannot_add_self(self, user_session):
        r = user_session.post(f"{API}/friends/request/{user_session.user_id}", timeout=15)
        assert r.status_code == 400

    def test_duplicate_request_rejected(self, user_session, second_user_session):
        r = user_session.post(f"{API}/friends/request/{second_user_session.user_id}", timeout=15)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Data hygiene
# ---------------------------------------------------------------------------
class TestDataHygiene:
    def test_no_mongo_id_anywhere(self):
        # games, featured, reviews, guides, help
        endpoints = [
            f"{API}/games",
            f"{API}/games/featured",
            f"{API}/games/elden-ring",
            f"{API}/games/elden-ring/reviews",
            f"{API}/games/elden-ring/guides",
            f"{API}/help-requests",
        ]
        for ep in endpoints:
            r = requests.get(ep, timeout=15)
            assert r.status_code == 200, f"{ep} -> {r.status_code}"
            assert "\"_id\"" not in r.text, f"Leaked _id at {ep}"
