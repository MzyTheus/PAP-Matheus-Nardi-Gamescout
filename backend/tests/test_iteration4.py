"""
GameScout Iteration 4 backend pytest suite.

Covers:
  - DELETE /api/friends/{user_id} (cancel pending, reject, remove accepted)
  - POST /api/users/me/avatar (multipart upload, MIME / size validation)
  - PATCH /api/users/me with picture URL + propagation to reviews/guides/help
  - GET /api/games/top (Bayesian-weighted ranking)
  - PATCH/DELETE on reviews/guides/help-requests + replies (owner-only)
  - Catalog size & franchise coverage (~900 games incl. RE / FNAF / Minecraft / Terraria / NMS / DBD)

Run:
  pytest /app/backend/tests/test_iteration4.py -v --tb=short \
    --junitxml=/app/test_reports/pytest/iteration4_results.xml
"""
import io
import os
import uuid
import struct
import zlib
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gamescout-reviews.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@gamescout.pt"
ADMIN_PASSWORD = "admin123"

RUN = uuid.uuid4().hex[:8]


# Resolve real game slugs once (catalog now uses IGDB IDs like 'igdb-119133')
_resolved_games: dict[str, str] = {}


def _resolve(query: str) -> str:
    if query in _resolved_games:
        return _resolved_games[query]
    r = requests.get(f"{API}/games", params={"q": query, "limit": 1}, timeout=20)
    assert r.status_code == 200, r.text
    games = r.json()
    assert games, f"No game found for query '{query}'"
    _resolved_games[query] = games[0]["game_id"]
    return games[0]["game_id"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_png(size_bytes: int = 0) -> bytes:
    """Build a minimally-valid PNG of an arbitrary byte size by padding with
    a single huge tEXt chunk after IDAT. The browser/server only checks MIME
    and total size, so this is sufficient for upload tests."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(typ: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(typ + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", crc)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00\xff\xff\xff"  # 1 scanline RGB white
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    base = sig + ihdr + idat + iend
    if size_bytes and len(base) < size_bytes:
        # Insert a big tEXt chunk before IEND
        pad_len = size_bytes - len(base) - 12 - 9  # chunk overhead
        text = b"Comment\x00" + b"A" * max(0, pad_len)
        text_chunk = chunk(b"tEXt", text)
        base = sig + ihdr + idat + text_chunk + iend
    return base


def _register(suffix: str):
    s = requests.Session()
    email = f"TEST_i4_{suffix}_{RUN}@gamescout.pt"
    r = s.post(f"{API}/auth/register",
               json={"email": email, "password": "tester123", "name": f"TEST i4 {suffix} {RUN}"},
               timeout=20)
    assert r.status_code == 200, r.text
    s.user_id = r.json()["user_id"]
    s.email = email
    return s


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
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
    return _register("C")


# ---------------------------------------------------------------------------
# Catalog & franchise coverage
# ---------------------------------------------------------------------------
class TestCatalog:
    def test_catalog_has_at_least_850_games(self):
        r = requests.get(f"{API}/games/meta", timeout=60)
        assert r.status_code == 200
        total = r.json()["total"]
        assert total >= 850, f"Catalog only has {total} games (expected >=850)"

    @pytest.mark.parametrize("query", [
        "Resident Evil",
        "Five Nights at Freddy",
        "Minecraft",
        "Terraria",
        "No Man",          # No Man's Sky
        "Dead by Daylight",
    ])
    def test_franchise_present(self, query):
        r = requests.get(f"{API}/games", params={"q": query, "limit": 50}, timeout=60)
        assert r.status_code == 200, r.text
        games = r.json()
        assert len(games) >= 1, f"No games found for franchise query '{query}'"


# ---------------------------------------------------------------------------
# Bayesian ranking
# ---------------------------------------------------------------------------
class TestTopGames:
    def test_top_basic_sort_and_min_count(self):
        r = requests.get(f"{API}/games/top", params={"limit": 20}, timeout=20)
        assert r.status_code == 200, r.text
        games = r.json()
        assert len(games) >= 1
        scores = [g.get("bayesian_score") for g in games]
        assert all(s is not None for s in scores), "missing bayesian_score on some game"
        # sorted desc
        assert scores == sorted(scores, reverse=True), "Top games not sorted by bayesian_score desc"
        # all have rating_count >= 5
        for g in games:
            assert g.get("rating_count", 0) >= 5, f"{g.get('title')} has rating_count {g.get('rating_count')}"

    def test_top_filter_genre_and_platform(self):
        r = requests.get(f"{API}/games/top",
                         params={"limit": 10, "genre": "RPG", "platform": "pc"}, timeout=20)
        assert r.status_code == 200
        games = r.json()
        for g in games:
            assert "RPG" in g.get("genres", [])
            assert "pc" in g.get("platforms", [])
            assert g.get("rating_count", 0) >= 5

    def test_top_no_low_count_outliers(self):
        """Bayesian ranking should not let 1 review = 100 ratings rule the top."""
        r = requests.get(f"{API}/games/top", params={"limit": 5}, timeout=20)
        assert r.status_code == 200
        for g in r.json():
            # Reasonable confidence floor — IGDB top-tier games normally have >=100
            assert g["rating_count"] >= 5
            # Top should be high quality
            assert g["rating"] >= 70, f"Top game {g['title']} has unusually low rating {g['rating']}"


# ---------------------------------------------------------------------------
# Avatar upload
# ---------------------------------------------------------------------------
class TestAvatar:
    def test_upload_png_avatar_returns_data_url(self, user_a):
        png = _make_png()
        files = {"file": ("avatar.png", png, "image/png")}
        r = user_a.post(f"{API}/users/me/avatar", files=files, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["picture"].startswith("data:image/png;base64,")
        # Persists on /auth/me
        me = user_a.get(f"{API}/auth/me", timeout=15).json()
        assert me["picture"].startswith("data:image/png;base64,")

    def test_upload_rejects_non_image(self, user_a):
        files = {"file": ("hack.txt", b"hello", "text/plain")}
        r = user_a.post(f"{API}/users/me/avatar", files=files, timeout=15)
        assert r.status_code == 400, f"Expected 400, got {r.status_code} {r.text}"

    def test_upload_rejects_too_large(self, user_a):
        big = _make_png(size_bytes=1_700_000)  # >1.5 MB
        assert len(big) > 1_500_000, f"helper produced {len(big)} bytes"
        files = {"file": ("big.png", big, "image/png")}
        r = user_a.post(f"{API}/users/me/avatar", files=files, timeout=30)
        assert r.status_code == 413, f"Expected 413, got {r.status_code} {r.text}"

    def test_avatar_propagates_to_review_user_picture(self, user_a):
        """Upload avatar, then create review, verify denormalized user_picture."""
        png = _make_png()
        r0 = user_a.post(f"{API}/users/me/avatar",
                         files={"file": ("a.png", png, "image/png")}, timeout=30)
        assert r0.status_code == 200
        new_pic = r0.json()["picture"]

        # Create a review (will have user_picture snapshot)
        game_id = _resolve("Minecraft")
        rv = user_a.post(f"{API}/games/{game_id}/reviews",
                         json={"rating": 7, "note": "TEST i4 propagation"}, timeout=20)
        assert rv.status_code == 200, rv.text

        # Now change picture via PATCH /users/me with URL → must propagate
        new_url = f"https://example.com/avatar_{RUN}.jpg"
        r1 = user_a.patch(f"{API}/users/me", json={"picture": new_url}, timeout=20)
        assert r1.status_code == 200
        assert r1.json()["picture"] == new_url

        # Verify the existing review now reflects the new picture (propagation)
        revs = requests.get(f"{API}/games/{game_id}/reviews", timeout=15).json()
        mine = [r for r in revs if r["user_id"] == user_a.user_id]
        assert mine, "Review not found after propagation"
        assert mine[0]["user_picture"] == new_url, (
            f"Expected denormalized user_picture to be {new_url}, "
            f"got {mine[0]['user_picture']}"
        )


# ---------------------------------------------------------------------------
# Reviews — PATCH/DELETE owner-only
# ---------------------------------------------------------------------------
class TestReviewsCrud:
    def _create_review(self, sess, query="Terraria", note="TEST review"):
        game_id = _resolve(query)
        r = sess.post(f"{API}/games/{game_id}/reviews",
                      json={"rating": 6, "note": note}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        d["__game_id"] = game_id
        return d

    def test_patch_review_by_owner_recomputes_complete(self, user_b):
        rev = self._create_review(user_b, "Terraria", "TEST patch start")
        rid = rev["review_id"]
        assert rev["is_complete"] is False

        # Promote to complete
        payload = {
            "rating": 9, "hours_played": 40, "graphics": 8, "story": 7,
            "tutorial": 7, "gameplay": 9, "recommends": True, "platform": "pc",
            "note": "Atualização de teste suficientemente longa.",
        }
        r = user_b.patch(f"{API}/reviews/{rid}", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["is_complete"] is True
        assert r.json()["rating"] == 9

    def test_patch_review_non_owner_403(self, user_b, user_c):
        rev = self._create_review(user_b, "No Man", "TEST other user")
        rid = rev["review_id"]
        r = user_c.patch(f"{API}/reviews/{rid}",
                         json={"rating": 1, "note": "hax"}, timeout=15)
        assert r.status_code == 403

    def test_delete_review_non_owner_403(self, user_b, user_c):
        rev = self._create_review(user_b, "Dead by Daylight", "TEST del other")
        rid = rev["review_id"]
        r = user_c.delete(f"{API}/reviews/{rid}", timeout=15)
        assert r.status_code == 403

    def test_delete_review_by_owner(self, user_b):
        rev = self._create_review(user_b, "Five Nights at Freddy", "TEST del owner")
        rid = rev["review_id"]
        gid = rev["__game_id"]
        r = user_b.delete(f"{API}/reviews/{rid}", timeout=15)
        assert r.status_code == 200
        # Confirm gone
        revs = requests.get(f"{API}/games/{gid}/reviews", timeout=15).json()
        assert not any(rv["review_id"] == rid for rv in revs)


# ---------------------------------------------------------------------------
# Guides — PATCH/DELETE owner-only (admin can author)
# ---------------------------------------------------------------------------
class TestGuidesCrud:
    @pytest.fixture(scope="class")
    def admin_guide(self, admin_session):
        game_id = _resolve("Elden Ring")
        r = admin_session.post(f"{API}/games/{game_id}/guides",
                               json={"title": f"TEST g4 {RUN}",
                                     "content": "Conteúdo bastante longo de teste.",
                                     "category": "tutorial"},
                               timeout=20)
        assert r.status_code == 200, r.text
        return r.json()

    def test_patch_guide_by_owner(self, admin_session, admin_guide):
        gid = admin_guide["guide_id"]
        r = admin_session.patch(f"{API}/guides/{gid}",
                                json={"title": f"TEST g4 patched {RUN}",
                                      "content": "Conteúdo atualizado de teste.",
                                      "category": "dica"},
                                timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["title"] == f"TEST g4 patched {RUN}"

    def test_patch_guide_non_owner_403(self, admin_guide, user_a):
        gid = admin_guide["guide_id"]
        r = user_a.patch(f"{API}/guides/{gid}",
                         json={"title": "hax", "content": "x" * 30, "category": "dica"},
                         timeout=15)
        assert r.status_code == 403

    def test_delete_guide_non_owner_403(self, admin_guide, user_a):
        gid = admin_guide["guide_id"]
        r = user_a.delete(f"{API}/guides/{gid}", timeout=15)
        assert r.status_code == 403

    def test_delete_guide_by_owner(self, admin_session, admin_guide):
        gid = admin_guide["guide_id"]
        r = admin_session.delete(f"{API}/guides/{gid}", timeout=15)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Help requests + replies CRUD
# ---------------------------------------------------------------------------
class TestHelpCrud:
    @pytest.fixture(scope="class")
    def help_thread(self, user_a, admin_session):
        game_id = _resolve("Elden Ring")
        r = user_a.post(f"{API}/help-requests",
                        json={"title": f"TEST help {RUN}",
                              "content": "Preciso ajuda detalhada.",
                              "kind": "ajuda",
                              "game_id": game_id},
                        timeout=20)
        assert r.status_code == 200, r.text
        help_id = r.json()["help_id"]

        rep = admin_session.post(f"{API}/help-requests/{help_id}/replies",
                                 json={"content": "Resposta inicial admin"},
                                 timeout=20)
        assert rep.status_code == 200, rep.text
        # Look up reply_id
        listing = requests.get(f"{API}/help-requests", timeout=15).json()
        target = next(h for h in listing if h["help_id"] == help_id)
        reply_id = target["replies"][-1]["reply_id"]
        return {"help_id": help_id, "reply_id": reply_id, "game_id": game_id}

    def test_patch_help_by_owner(self, user_a, help_thread):
        hid = help_thread["help_id"]
        r = user_a.patch(f"{API}/help-requests/{hid}",
                         json={"title": f"TEST help upd {RUN}",
                               "content": "Conteúdo editado",
                               "kind": "ajuda",
                               "game_id": help_thread["game_id"]},
                         timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["title"] == f"TEST help upd {RUN}"

    def test_patch_help_non_owner_403(self, user_b, help_thread):
        hid = help_thread["help_id"]
        r = user_b.patch(f"{API}/help-requests/{hid}",
                         json={"title": "hax", "content": "x", "kind": "ajuda"},
                         timeout=15)
        assert r.status_code == 403

    def test_patch_reply_by_author(self, admin_session, help_thread):
        r = admin_session.patch(
            f"{API}/help-requests/{help_thread['help_id']}/replies/{help_thread['reply_id']}",
            json={"content": "Resposta editada admin"},
            timeout=15,
        )
        assert r.status_code == 200, r.text

    def test_patch_reply_non_author_403(self, user_b, help_thread):
        r = user_b.patch(
            f"{API}/help-requests/{help_thread['help_id']}/replies/{help_thread['reply_id']}",
            json={"content": "hax"},
            timeout=15,
        )
        assert r.status_code == 403

    def test_delete_reply_non_author_403(self, user_b, help_thread):
        r = user_b.delete(
            f"{API}/help-requests/{help_thread['help_id']}/replies/{help_thread['reply_id']}",
            timeout=15,
        )
        assert r.status_code == 403

    def test_delete_reply_by_author(self, admin_session, help_thread):
        r = admin_session.delete(
            f"{API}/help-requests/{help_thread['help_id']}/replies/{help_thread['reply_id']}",
            timeout=15,
        )
        assert r.status_code == 200

    def test_delete_help_non_owner_403(self, user_b, help_thread):
        r = user_b.delete(f"{API}/help-requests/{help_thread['help_id']}", timeout=15)
        assert r.status_code == 403

    def test_delete_help_by_owner(self, user_a, help_thread):
        r = user_a.delete(f"{API}/help-requests/{help_thread['help_id']}", timeout=15)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Friends DELETE — three flavours
# ---------------------------------------------------------------------------
class TestFriendsDelete:
    def test_cancel_pending_outgoing(self, user_a, user_b):
        # A -> B
        r = user_a.post(f"{API}/friends/request/{user_b.user_id}", timeout=15)
        assert r.status_code == 200, r.text

        # A cancels
        r = user_a.delete(f"{API}/friends/{user_b.user_id}", timeout=15)
        assert r.status_code == 200, r.text

        # B should no longer see incoming request
        reqs = user_b.get(f"{API}/friends/requests", timeout=15).json()
        assert not any(rq["from_user"]["user_id"] == user_a.user_id for rq in reqs)

    def test_reject_incoming(self, user_a, user_b):
        # A -> B
        r = user_a.post(f"{API}/friends/request/{user_b.user_id}", timeout=15)
        assert r.status_code == 200

        # B rejects (DELETE on user_a)
        r = user_b.delete(f"{API}/friends/{user_a.user_id}", timeout=15)
        assert r.status_code == 200

    def test_remove_accepted_friendship(self, user_a, user_b):
        # Setup: A -> B, B accepts
        r = user_a.post(f"{API}/friends/request/{user_b.user_id}", timeout=15)
        assert r.status_code == 200
        r = user_b.post(f"{API}/friends/accept/{user_a.user_id}", timeout=15)
        assert r.status_code == 200

        # Now A removes B
        r = user_a.delete(f"{API}/friends/{user_b.user_id}", timeout=15)
        assert r.status_code == 200

        # Both lists should be empty for each other
        f1 = user_a.get(f"{API}/friends", timeout=15).json()
        f2 = user_b.get(f"{API}/friends", timeout=15).json()
        assert not any(f["user_id"] == user_b.user_id for f in f1)
        assert not any(f["user_id"] == user_a.user_id for f in f2)

    def test_delete_nonexistent_returns_404(self, user_a, user_c):
        # Nothing between A and C now
        r = user_a.delete(f"{API}/friends/{user_c.user_id}", timeout=15)
        assert r.status_code == 404
