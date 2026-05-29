"""GameScout backend - FastAPI + MongoDB.
Auth: dual flow (JWT email/password + Emergent Google session_token).
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import asyncio
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
import requests
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Query
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from seed import GAMES_SEED
import igdb as igdb_mod

# Resend (transactional email) — optional; fails-soft if key missing
try:
    import resend as _resend
    _resend.api_key = os.environ.get("RESEND_API_KEY", "")
except Exception:  # pragma: no cover
    _resend = None

# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gamescout")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
PLATFORM_VALUES = ["xbox-360", "xbox-one", "xbox-series-x", "ps3", "ps4", "ps5", "pc", "switch", "mobile"]


class SocialLinks(BaseModel):
    discord: Optional[str] = None
    tiktok: Optional[str] = None
    instagram: Optional[str] = None
    twitch: Optional[str] = None


class GamePref(BaseModel):
    favorite_game: Optional[str] = None
    favorite_game_id: Optional[str] = None
    platforms: List[str] = []
    pc_specs: Optional[str] = None


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: EmailStr
    name: str
    bio: Optional[str] = ""
    picture: Optional[str] = None
    role: str = "user"
    points: int = 0
    auth_provider: str = "email"
    social: SocialLinks = SocialLinks()
    prefs: GamePref = GamePref()
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=2)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleSessionIn(BaseModel):
    session_id: str


class ProfileUpdateIn(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    picture: Optional[str] = None
    social: Optional[SocialLinks] = None
    prefs: Optional[GamePref] = None


class Game(BaseModel):
    model_config = ConfigDict(extra="ignore")
    game_id: str
    title: str
    cover: str
    year: int
    genres: List[str]
    platforms: List[str]
    developer: str
    description: str


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=10)
    hours_played: Optional[int] = Field(default=None, ge=0)
    graphics: Optional[int] = Field(default=None, ge=1, le=10)
    story: Optional[int] = Field(default=None, ge=1, le=10)
    tutorial: Optional[int] = Field(default=None, ge=1, le=10)
    gameplay: Optional[int] = Field(default=None, ge=1, le=10)
    audio: Optional[int] = Field(default=None, ge=1, le=10)
    performance: Optional[int] = Field(default=None, ge=1, le=10)
    fun: Optional[int] = Field(default=None, ge=1, le=10)
    recommends: Optional[bool] = None
    platform: Optional[str] = None
    note: Optional[str] = ""


class Review(ReviewIn):
    review_id: str
    game_id: str
    user_id: str
    user_name: str
    user_picture: Optional[str] = None
    is_complete: bool
    score: float
    created_at: datetime
    updated_at: datetime


class GuideIn(BaseModel):
    title: str = Field(min_length=3)
    content: str = Field(min_length=20)
    category: Literal["dica", "tutorial", "como-zerar", "estrategia", "macete"] = "dica"


class HelpRequestIn(BaseModel):
    title: str = Field(min_length=3)
    content: str
    game_id: Optional[str] = None
    kind: Literal["dica", "jogar-junto", "ajuda"] = "ajuda"


class HelpReplyIn(BaseModel):
    content: str = Field(min_length=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


# Only Gmail accounts can register/login (per product spec).
def is_gmail(email: str) -> bool:
    return (email or "").lower().strip().endswith("@gmail.com")


def gen_verification_code() -> str:
    """6-digit numeric code for email verification."""
    return f"{secrets.randbelow(1_000_000):06d}"


async def send_verification_email(to_email: str, name: str, code: str) -> bool:
    """Fire-and-forget email send via Resend. Logs and returns False on failure."""
    if not _resend or not os.environ.get("RESEND_API_KEY"):
        log.warning("Resend not configured — skipping email to %s (code=%s)", to_email, code)
        return False
    sender = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;background:#0a0a0a;color:#fff;border-radius:6px">
      <div style="font-size:24px;font-weight:900;letter-spacing:-0.5px;text-transform:uppercase">
        Game<span style="color:#ff6a00">Scout</span>
      </div>
      <h2 style="font-weight:700;margin-top:18px">Olá, {name}!</h2>
      <p style="color:#bbb;line-height:1.5">Confirma o teu email para ativares a tua conta no GameScout.</p>
      <div style="background:#171717;border:1px solid #ff6a00;border-radius:4px;padding:18px;margin:18px 0;text-align:center">
        <div style="color:#ff6a00;font-size:11px;letter-spacing:3px;text-transform:uppercase;margin-bottom:6px">O teu código</div>
        <div style="font-family:'Courier New',monospace;font-size:36px;font-weight:900;letter-spacing:8px">{code}</div>
      </div>
      <p style="color:#888;font-size:12px">Este código expira em 30 minutos. Se não foste tu, ignora este email.</p>
      <p style="color:#666;font-size:11px;margin-top:30px">— Equipa GameScout</p>
    </div>
    """
    try:
        await asyncio.to_thread(
            _resend.Emails.send,
            {
                "from": f"GameScout <{sender}>",
                "to": [to_email],
                "subject": "GameScout · Confirma o teu email",
                "html": html,
            },
        )
        return True
    except Exception as e:
        log.error("Failed to send verification email to %s: %s", to_email, e)
        return False


async def issue_verification_code(user_id: str, email: str, name: str) -> None:
    """Generate and store a 6-digit code, then send by email (best-effort)."""
    code = gen_verification_code()
    await db.email_verifications.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "email": email,
            "code": code,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
            "attempts": 0,
        }},
        upsert=True,
    )
    await send_verification_email(email, name, code)


def make_jwt(user_id: str, kind: str, ttl: timedelta) -> str:
    return jwt.encode(
        {"sub": user_id, "type": kind, "exp": datetime.now(timezone.utc) + ttl},
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


def set_jwt_cookies(resp: Response, user_id: str):
    access = make_jwt(user_id, "access", timedelta(minutes=60))
    refresh = make_jwt(user_id, "refresh", timedelta(days=7))
    resp.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=3600, path="/")
    resp.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")


def public_user(u: dict) -> dict:
    out = {k: v for k, v in u.items() if k not in ("_id", "password_hash")}
    if "created_at" in out and isinstance(out["created_at"], datetime):
        out["created_at"] = out["created_at"].isoformat()
    return out


RANK_LEVELS = [
    ("Novato", 0),
    ("Explorador", 50),
    ("Aventureiro", 250),
    ("Avaliador", 1000),
    ("Apreciador de Obras", 5000),
]


def rank_for_points(pts: int) -> dict:
    current = RANK_LEVELS[0]
    nxt = None
    for i, (name, threshold) in enumerate(RANK_LEVELS):
        if pts >= threshold:
            current = (name, threshold)
            nxt = RANK_LEVELS[i + 1] if i + 1 < len(RANK_LEVELS) else None
    return {
        "name": current[0],
        "min_points": current[1],
        "next_name": nxt[0] if nxt else None,
        "next_points": nxt[1] if nxt else None,
        "level": [n for n, _ in RANK_LEVELS].index(current[0]) + 1,
    }


async def get_current_user_optional(request: Request) -> Optional[dict]:
    # 1) Emergent session_token
    st = request.cookies.get("session_token")
    if st:
        sess = await db.user_sessions.find_one({"session_token": st}, {"_id": 0})
        if sess:
            exp = sess.get("expires_at")
            if isinstance(exp, str):
                exp = datetime.fromisoformat(exp)
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp and exp > datetime.now(timezone.utc):
                user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0, "password_hash": 0})
                if user:
                    return user

    # 2) JWT cookie or bearer
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("type") != "access":
            return None
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        return user
    except jwt.PyJWTError:
        return None


async def get_current_user(request: Request) -> dict:
    u = await get_current_user_optional(request)
    if not u:
        raise HTTPException(401, "Não autenticado")
    # Reject suspended users (admins exempt — admin can still operate even if flagged)
    su = u.get("suspended_until")
    if su and u.get("role") != "admin":
        if isinstance(su, str):
            try: su = datetime.fromisoformat(su)
            except Exception: su = None
        if su and su.tzinfo is None: su = su.replace(tzinfo=timezone.utc)
        if su and su > datetime.now(timezone.utc):
            raise HTTPException(403, f"Conta suspensa até {su.isoformat()}: {u.get('suspended_reason') or 'violação das regras'}")
    return u


async def get_verified_user(request: Request) -> dict:
    """Same as get_current_user but blocks unverified email users.
    Google-auth users are pre-verified so they pass through."""
    u = await get_current_user(request)
    if u.get("auth_provider") == "email" and not u.get("email_verified", False):
        raise HTTPException(403, "Confirma o teu email para realizar esta ação")
    return u


async def award_points(user_id: str, pts: int):
    await db.users.update_one({"user_id": user_id}, {"$inc": {"points": pts}})


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="GameScout API")
api = APIRouter(prefix="/api")


def gen_user_id() -> str:
    """Format: U{year}{LETTER}{4-alnum}, e.g. U2026M4X92."""
    import random, string
    year = datetime.now(timezone.utc).year
    letter = random.choice(string.ascii_uppercase)
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"U{year}{letter}{suffix}"


async def propagate_user_changes(user_id: str, fields: dict):
    """Keep denormalized user info in reviews/guides/help in sync."""
    name = fields.get("name")
    pic = fields.get("picture")
    rev_set = {}
    if name is not None: rev_set["user_name"] = name
    if pic is not None: rev_set["user_picture"] = pic
    if rev_set:
        await db.reviews.update_many({"user_id": user_id}, {"$set": rev_set})
    g_set = {}
    if name is not None: g_set["author_name"] = name
    if pic is not None: g_set["author_picture"] = pic
    if g_set:
        await db.guides.update_many({"author_id": user_id}, {"$set": g_set})
        await db.help_requests.update_many({"author_id": user_id}, {"$set": g_set})
        # replies inside help_requests
        h_set = {}
        if name is not None: h_set["replies.$[r].author_name"] = name
        if pic is not None: h_set["replies.$[r].author_picture"] = pic
        if h_set:
            await db.help_requests.update_many(
                {"replies.author_id": user_id},
                {"$set": h_set},
                array_filters=[{"r.author_id": user_id}],
            )


async def get_friendship_status(viewer_id: str, target_id: str) -> str:
    """Returns: 'self' | 'accepted' | 'pending_sent' | 'pending_received' | 'none'."""
    if viewer_id == target_id:
        return "self"
    f = await db.friendships.find_one({
        "$or": [
            {"from_user": viewer_id, "to_user": target_id},
            {"from_user": target_id, "to_user": viewer_id},
        ]
    }, {"_id": 0})
    if not f:
        return "none"
    if f.get("status") == "accepted":
        return "accepted"
    if f["from_user"] == viewer_id:
        return "pending_sent"
    return "pending_received"


@app.on_event("startup")
async def startup():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.games.create_index("game_id", unique=True)
    await db.games.create_index("genres")
    await db.games.create_index("platforms")
    await db.games.create_index("rating")
    await db.games.create_index("year")
    await db.reviews.create_index([("game_id", 1), ("user_id", 1)], unique=True)
    await db.guides.create_index("game_id")
    await db.help_requests.create_index("created_at")
    await db.friendships.create_index([("from_user", 1), ("to_user", 1)], unique=True)
    await db.messages.create_index("created_at")
    await db.messages.create_index([("thread_key", 1), ("created_at", 1)])
    await db.communities.create_index("community_id", unique=True)
    await db.communities.create_index("name")
    await db.email_verifications.create_index("user_id", unique=True)
    await db.email_verifications.create_index("expires_at", expireAfterSeconds=0)

    # Seed admin (legacy local admin — kept for emergency access via Gmail-only filter,
    # this account will be unable to log in normally so we leave it as DB seed only).
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@gamescout.pt")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "user_id": gen_user_id(),
            "email": admin_email,
            "name": "Admin",
            "password_hash": hash_password(admin_password),
            "role": "admin",
            "points": 10000,
            "bio": "Curador da comunidade GameScout",
            "picture": None,
            "auth_provider": "email",
            "email_verified": True,
            "social": {},
            "prefs": {"platforms": ["pc"], "favorite_game": None, "pc_specs": None},
            "created_at": datetime.now(timezone.utc),
        })
        log.info("Admin seeded: %s", admin_email)
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})

    # Promote configured Gmail to admin role (idempotent). Also seed it on first
    # boot so it has a known password — required since email/password is the
    # only login flow available for non-Google users.
    target_admin = (os.environ.get("ADMIN_GMAIL") or "").lower().strip()
    target_pwd = os.environ.get("ADMIN_GMAIL_PASSWORD", "")
    if target_admin:
        # Demote any other admin accounts (only the canonical Gmail admin)
        await db.users.update_many(
            {"role": "admin", "email": {"$ne": target_admin}},
            {"$set": {"role": "user"}},
        )
        existing_admin = await db.users.find_one({"email": target_admin})
        if not existing_admin and target_pwd:
            await db.users.insert_one({
                "user_id": gen_user_id(),
                "email": target_admin,
                "name": "Matheus Vittore",
                "password_hash": hash_password(target_pwd),
                "role": "admin",
                "points": 10000,
                "bio": "Administrador GameScout",
                "picture": None,
                "auth_provider": "email",
                "email_verified": True,
                "social": {},
                "prefs": {"platforms": ["pc"], "favorite_game": None, "favorite_game_id": None, "pc_specs": None},
                "created_at": datetime.now(timezone.utc),
            })
            log.info("Admin Gmail seeded: %s", target_admin)
        else:
            upd = {"role": "admin", "email_verified": True}
            if target_pwd:
                upd["password_hash"] = hash_password(target_pwd)
            await db.users.update_one({"email": target_admin}, {"$set": upd})
            log.info("Promoted %s to admin", target_admin)

    # Game catalog: import from IGDB on startup, then schedule periodic refresh
    asyncio.create_task(_refresh_games_catalog())
    asyncio.create_task(_periodic_refresh_loop())

    # One-time backfill: compute `score` for legacy reviews that don't have it.
    asyncio.create_task(_backfill_review_scores())

    # One-time cleanup: remove TEST_/dev seed data so ranking is clean.
    asyncio.create_task(_cleanup_test_data())


async def _cleanup_test_data():
    """Delete TEST_-prefixed users, their reviews, friendships, and dev communities
    so the leaderboard and chat data are clean in production.
    Idempotent — safe to run on every startup.
    """
    try:
        # Find ephemeral test users: emails starting with TEST_ or matching dev patterns.
        test_user_cur = db.users.find(
            {"email": {"$regex": r"^(TEST_|test_|tester|smoke_|qa_)", "$options": "i"}},
            {"_id": 0, "user_id": 1, "email": 1},
        )
        test_user_ids = [u["user_id"] async for u in test_user_cur]
        if test_user_ids:
            r = await db.reviews.delete_many({"user_id": {"$in": test_user_ids}})
            await db.guides.delete_many({"author_id": {"$in": test_user_ids}})
            await db.help_requests.delete_many({"author_id": {"$in": test_user_ids}})
            await db.friendships.delete_many({"$or": [{"from_user": {"$in": test_user_ids}}, {"to_user": {"$in": test_user_ids}}]})
            await db.wishlists.delete_many({"user_id": {"$in": test_user_ids}})
            await db.messages.delete_many({"sender_id": {"$in": test_user_ids}})
            await db.users.delete_many({"user_id": {"$in": test_user_ids}})
            log.info("Cleaned %d test users + %d reviews", len(test_user_ids), r.deleted_count)
        # Test communities (created by automated test suites)
        cr = await db.communities.delete_many({"name": {"$regex": r"^(TEST|test |smoke )", "$options": "i"}})
        if cr.deleted_count:
            log.info("Cleaned %d test communities", cr.deleted_count)
    except Exception as e:
        log.warning("Cleanup failed: %s", e)


async def _backfill_review_scores():
    """Ensure every review has a computed `score` so /games/top aggregations work."""
    cur = db.reviews.find({"score": {"$exists": False}}, {"_id": 0})
    count = 0
    async for r in cur:
        cat_values = [r.get(c) for c in REVIEW_CATEGORIES if r.get(c) is not None]
        if cat_values:
            cat_avg = sum(cat_values) / len(cat_values)
            score = round((r.get("rating", 0) + cat_avg) / 2, 2)
        else:
            score = float(r.get("rating", 0))
        await db.reviews.update_one({"review_id": r["review_id"]}, {"$set": {"score": score}})
        count += 1
    if count:
        log.info("Backfilled score on %d legacy reviews", count)


async def _refresh_games_catalog():
    cid = os.environ.get("TWITCH_CLIENT_ID")
    cs = os.environ.get("TWITCH_CLIENT_SECRET")
    limit = int(os.environ.get("IGDB_IMPORT_LIMIT", "500"))
    existing = await db.games.count_documents({})
    if not cid or not cs:
        log.warning("IGDB credentials missing — falling back to local seed (%d games)", len(GAMES_SEED))
        if existing == 0:
            for g in GAMES_SEED:
                await db.games.update_one({"game_id": g["game_id"]}, {"$setOnInsert": g}, upsert=True)
        return
    try:
        loop = asyncio.get_running_loop()
        games = await loop.run_in_executor(None, igdb_mod.fetch_games, cid, cs, limit)
        if not games:
            raise RuntimeError("IGDB returned no games")
        # Save games with English descriptions immediately
        await db.games.delete_many({})
        await db.games.insert_many([{**g} for g in games])
        await db.meta.update_one({"_id": "games"}, {"$set": {"last_imported_at": datetime.now(timezone.utc).isoformat(), "count": len(games)}}, upsert=True)
        log.info("IGDB import complete: %d games (descriptions in EN; translation queued)", len(games))
        # Translate in background, updating each game as it goes
        asyncio.create_task(_translate_pending_descriptions())
    except Exception as e:
        log.error("IGDB import failed: %s — keeping existing %d games", e, existing)
        if existing == 0:
            for g in GAMES_SEED:
                await db.games.update_one({"game_id": g["game_id"]}, {"$setOnInsert": g}, upsert=True)


async def _translate_pending_descriptions():
    """Translate games whose `description` still equals `description_en`. Runs in a worker thread to avoid blocking the event loop."""
    if not os.environ.get("EMERGENT_LLM_KEY"):
        return
    cur = db.games.find(
        {"$expr": {"$eq": ["$description", "$description_en"]}, "description_en": {"$ne": ""}},
        {"_id": 0, "game_id": 1, "title": 1, "description_en": 1},
    )
    pending = [g async for g in cur]
    if not pending:
        log.info("Translation: nothing pending")
        return
    log.info("Translation: %d games to translate", len(pending))
    BATCH = 10
    for i in range(0, len(pending), BATCH):
        chunk = pending[i:i + BATCH]
        # Translate in a separate thread so the event loop stays responsive
        def _do_chunk(c=chunk):
            import asyncio as _a
            loop = _a.new_event_loop()
            try:
                loop.run_until_complete(igdb_mod.translate_descriptions_batch(c, batch_size=BATCH))
            finally:
                loop.close()
        await asyncio.get_running_loop().run_in_executor(None, _do_chunk)
        for g in chunk:
            new_desc = g.get("description")
            if new_desc and new_desc != g.get("description_en"):
                await db.games.update_one({"game_id": g["game_id"]}, {"$set": {"description": new_desc}})
        log.info("Translation progress: %d/%d", min(i + BATCH, len(pending)), len(pending))
        await asyncio.sleep(0.3)
    log.info("Translation finished")


async def _periodic_refresh_loop():
    """Re-import IGDB catalog every IGDB_REFRESH_HOURS (default 168h = 7 days)."""
    interval_h = int(os.environ.get("IGDB_REFRESH_HOURS", "168"))
    interval_s = max(3600, interval_h * 3600)
    while True:
        await asyncio.sleep(interval_s)
        log.info("Periodic IGDB refresh triggered (every %dh)", interval_h)
        await _refresh_games_catalog()


@api.post("/admin/games/refresh")
async def admin_refresh_games(user: dict = Depends(get_current_user)):
    """Manually trigger IGDB re-import (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admin")
    asyncio.create_task(_refresh_games_catalog())
    return {"ok": True, "message": "Importação iniciada em background"}


@app.on_event("shutdown")
async def shutdown():
    client.close()


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    if not is_gmail(email):
        raise HTTPException(400, "Apenas contas Gmail são permitidas (@gmail.com)")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email já registado")
    user_id = gen_user_id()
    is_admin_email = email == os.environ.get("ADMIN_GMAIL", "").lower().strip()
    doc = {
        "user_id": user_id,
        "email": email,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
        "role": "admin" if is_admin_email else "user",
        "points": 10000 if is_admin_email else 0,
        "bio": "",
        "picture": None,
        "auth_provider": "email",
        "email_verified": False,
        "social": {},
        "prefs": {"platforms": [], "favorite_game": None, "favorite_game_id": None, "pc_specs": None},
        "created_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(doc)
    # Send verification code (best effort) — don't gate registration on email delivery
    await issue_verification_code(user_id, email, doc["name"])
    set_jwt_cookies(response, user_id)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    out = public_user(user)
    out["needs_verification"] = True
    return out


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response, request: Request):
    email = payload.email.lower().strip()
    if not is_gmail(email):
        raise HTTPException(400, "Apenas contas Gmail podem entrar (@gmail.com)")
    ip = request.client.host if request.client else "?"
    ident = f"{ip}:{email}"
    # brute force check
    attempt = await db.login_attempts.find_one({"identifier": ident})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if isinstance(locked_until, str):
            locked_until = datetime.fromisoformat(locked_until)
        if locked_until and locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until and locked_until > datetime.now(timezone.utc):
            raise HTTPException(429, "Demasiadas tentativas. Tente mais tarde.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True,
        )
        raise HTTPException(401, "Email ou password inválidos")
    await db.login_attempts.delete_one({"identifier": ident})
    set_jwt_cookies(response, user["user_id"])
    out = public_user(user)
    if not user.get("email_verified", False):
        out["needs_verification"] = True
        # Re-issue a fresh code so the user can complete verification right away
        await issue_verification_code(user["user_id"], email, user.get("name") or "")
    return out


@api.post("/auth/logout")
async def logout(response: Response, request: Request):
    st = request.cookies.get("session_token")
    if st:
        await db.user_sessions.delete_one({"session_token": st})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    out = public_user(user)
    out["needs_verification"] = (user.get("auth_provider") == "email") and (not user.get("email_verified", False))
    return out


class VerifyEmailIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


@api.post("/auth/verify-email")
async def verify_email(payload: VerifyEmailIn, user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        return {"ok": True, "already": True}
    rec = await db.email_verifications.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(400, "Sem código pendente. Pede um novo.")
    if rec.get("attempts", 0) >= 8:
        raise HTTPException(429, "Demasiadas tentativas. Pede um novo código.")
    exp = rec.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and exp < datetime.now(timezone.utc):
        raise HTTPException(400, "Código expirado. Pede um novo.")
    if (payload.code or "").strip() != rec.get("code"):
        await db.email_verifications.update_one({"user_id": user["user_id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(400, "Código incorreto")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"email_verified": True}})
    await db.email_verifications.delete_one({"user_id": user["user_id"]})
    return {"ok": True}


@api.post("/auth/resend-code")
async def resend_code(user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        return {"ok": True, "already": True}
    await issue_verification_code(user["user_id"], user["email"], user.get("name") or "")
    return {"ok": True}


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(401, "Sem refresh token")
    try:
        payload = jwt.decode(rt, JWT_SECRET, algorithms=[JWT_ALG])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Token inválido")
        access = make_jwt(payload["sub"], "access", timedelta(minutes=60))
        response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=3600, path="/")
        return {"ok": True}
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido")


@api.post("/auth/google/session")
async def google_session(payload: GoogleSessionIn, response: Response):
    """Exchange Emergent session_id for session_token; create/find user."""
    try:
        r = requests.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": payload.session_id}, timeout=10)
    except Exception as e:
        raise HTTPException(502, f"Falha a contactar Emergent Auth: {e}")
    if r.status_code != 200:
        raise HTTPException(401, "Sessão Google inválida")
    data = r.json()
    email = (data.get("email") or "").lower()
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture")
    session_token = data.get("session_token")
    if not email or not session_token:
        raise HTTPException(502, "Resposta inválida do Emergent")
    if not is_gmail(email):
        raise HTTPException(403, "Apenas contas Gmail são permitidas")

    user = await db.users.find_one({"email": email})
    is_admin_email = email == os.environ.get("ADMIN_GMAIL", "").lower().strip()
    if not user:
        user_id = gen_user_id()
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": "admin" if is_admin_email else "user",
            "points": 10000 if is_admin_email else 0,
            "bio": "",
            "auth_provider": "google",
            "email_verified": True,  # Google has already verified the address
            "social": {},
            "prefs": {"platforms": [], "favorite_game": None, "favorite_game_id": None, "pc_specs": None},
            "created_at": datetime.now(timezone.utc),
        })
        user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    else:
        upd = {}
        if picture and not user.get("picture"):
            upd["picture"] = picture
        if not user.get("email_verified"):
            upd["email_verified"] = True  # via Google
        if is_admin_email and user.get("role") != "admin":
            upd["role"] = "admin"
        if upd:
            await db.users.update_one({"email": email}, {"$set": upd})
        user.pop("_id", None)
        user.pop("password_hash", None)

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    response.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return public_user(user)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@api.get("/users/me/full")
async def me_full(user: dict = Depends(get_current_user)):
    u = public_user(user)
    u["rank"] = rank_for_points(u.get("points", 0))
    u["needs_verification"] = (user.get("auth_provider") == "email") and (not user.get("email_verified", False))
    return u


@api.patch("/users/me")
async def update_me(payload: ProfileUpdateIn, user: dict = Depends(get_verified_user)):
    update = {}
    if payload.name is not None: update["name"] = payload.name.strip()
    if payload.bio is not None: update["bio"] = payload.bio
    if payload.picture is not None: update["picture"] = payload.picture
    if payload.social is not None: update["social"] = payload.social.model_dump()
    if payload.prefs is not None: update["prefs"] = payload.prefs.model_dump()
    if update:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": update})
        await propagate_user_changes(user["user_id"], update)
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    out = public_user(fresh)
    out["rank"] = rank_for_points(out.get("points", 0))
    return out


@api.post("/users/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user: dict = Depends(get_verified_user)):
    """Upload an image as the user's avatar. Stored as data URL in user.picture."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Apenas imagens são permitidas")
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(400, "Formato não suportado (use JPG, PNG, WEBP ou GIF)")
    data = await file.read()
    if len(data) > 1_500_000:
        raise HTTPException(413, "Imagem demasiado grande (máx 1.5 MB)")
    import base64
    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:{file.content_type};base64,{b64}"
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"picture": data_url}})
    await propagate_user_changes(user["user_id"], {"picture": data_url})
    return {"picture": data_url}


@api.get("/users/search")
async def search_users(q: str = Query(min_length=2), user: dict = Depends(get_verified_user)):
    cur = db.users.find(
        {"name": {"$regex": q, "$options": "i"}, "user_id": {"$ne": user["user_id"]}},
        {"_id": 0, "password_hash": 0, "email": 0},
    ).limit(20)
    return [public_user(u) async for u in cur]


@api.get("/users/{user_id}")
async def get_user_public(user_id: str, request: Request):
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0, "email": 0})
    if not u:
        raise HTTPException(404, "Utilizador não encontrado")
    out = public_user(u)
    out["rank"] = rank_for_points(out.get("points", 0))
    review_count = await db.reviews.count_documents({"user_id": user_id})
    guide_count = await db.guides.count_documents({"author_id": user_id})
    wishlist_count = len(out.get("wishlist") or [])
    out["stats"] = {"reviews": review_count, "guides": guide_count, "wishlist": wishlist_count}
    fav_id = (out.get("prefs") or {}).get("favorite_game_id")
    if fav_id:
        g = await db.games.find_one({"game_id": fav_id}, {"_id": 0, "title": 1, "cover": 1, "game_id": 1})
        if g:
            out["prefs"]["favorite_game_doc"] = g
    viewer = await get_current_user_optional(request)
    out["friendship_status"] = await get_friendship_status(viewer["user_id"], user_id) if viewer else "none"
    return out


@api.get("/wishlist")
async def get_my_wishlist(user: dict = Depends(get_current_user)):
    ids = user.get("wishlist") or []
    if not ids:
        return []
    cur = db.games.find({"game_id": {"$in": ids}}, {"_id": 0})
    games = {g["game_id"]: g async for g in cur}
    # preserve original order (newest added last)
    return [games[i] for i in ids if i in games]


@api.post("/wishlist/{game_id}")
async def add_to_wishlist(game_id: str, user: dict = Depends(get_verified_user)):
    g = await db.games.find_one({"game_id": game_id}, {"_id": 0, "game_id": 1})
    if not g:
        raise HTTPException(404, "Jogo não encontrado")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$addToSet": {"wishlist": game_id}},
    )
    return {"ok": True, "in_wishlist": True}


@api.delete("/wishlist/{game_id}")
async def remove_from_wishlist(game_id: str, user: dict = Depends(get_verified_user)):
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$pull": {"wishlist": game_id}},
    )
    return {"ok": True, "in_wishlist": False}


@api.get("/users/{user_id}/wishlist")
async def get_user_wishlist(user_id: str):
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "wishlist": 1})
    if not u:
        raise HTTPException(404, "Utilizador não encontrado")
    ids = u.get("wishlist") or []
    if not ids:
        return []
    cur = db.games.find({"game_id": {"$in": ids}}, {"_id": 0})
    games = {g["game_id"]: g async for g in cur}
    return [games[i] for i in ids if i in games]


# ---------------------------------------------------------------------------
# Discover (recommendations)
# ---------------------------------------------------------------------------
@api.get("/discover")
async def discover(user: dict = Depends(get_verified_user)):
    """Recommend games based on user reviews + profile preferences."""
    user_id = user["user_id"]
    prefs = user.get("prefs") or {}
    user_platforms = prefs.get("platforms") or []
    fav_id = prefs.get("favorite_game_id")

    # Genres/platforms inferred from user's high-rated reviews (rating >= 7)
    seen_game_ids = set()
    liked_genres: dict = {}
    liked_platforms: dict = {}
    user_reviews_cur = db.reviews.find({"user_id": user_id}, {"_id": 0, "game_id": 1, "rating": 1})
    async for r in user_reviews_cur:
        seen_game_ids.add(r["game_id"])
        if r.get("rating", 0) >= 7:
            g = await db.games.find_one({"game_id": r["game_id"]}, {"_id": 0, "genres": 1, "platforms": 1})
            if g:
                for gen in g.get("genres") or []:
                    liked_genres[gen] = liked_genres.get(gen, 0) + 1
                for p in g.get("platforms") or []:
                    liked_platforms[p] = liked_platforms.get(p, 0) + 1

    # Add favorite game's genres
    if fav_id:
        g = await db.games.find_one({"game_id": fav_id}, {"_id": 0, "genres": 1, "platforms": 1})
        if g:
            for gen in g.get("genres") or []:
                liked_genres[gen] = liked_genres.get(gen, 0) + 2

    top_genres = sorted(liked_genres, key=lambda x: -liked_genres[x])[:3]
    target_platforms = list({*user_platforms, *list(liked_platforms.keys())[:3]})

    # Build sections
    async def by_filter(query, n=12):
        if seen_game_ids:
            query = {**query, "game_id": {"$nin": list(seen_game_ids)}}
        cur = db.games.find(query, {"_id": 0}).sort("rating", -1).limit(n)
        return [d async for d in cur]

    # Section 1: For your taste (matches top genres)
    by_taste = []
    if top_genres:
        by_taste = await by_filter({"genres": {"$in": top_genres}}, 12)

    # Section 2: For your platforms
    by_platform = []
    if target_platforms:
        by_platform = await by_filter({"platforms": {"$in": target_platforms}}, 12)

    # Section 3: Hidden gems (high rating, low review count)
    hidden = await by_filter({"rating": {"$gte": 80}}, 12)

    # Section 4: Trending (community recent reviews)
    pipeline = [
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$game_id", "n": {"$sum": 1}, "avg": {"$avg": "$rating"}}},
        {"$sort": {"n": -1}},
        {"$limit": 12},
    ]
    trending_ids = [d["_id"] async for d in db.reviews.aggregate(pipeline)]
    trending = []
    if trending_ids:
        cur = db.games.find({"game_id": {"$in": trending_ids}}, {"_id": 0})
        trending = [d async for d in cur]

    return {
        "summary": {
            "top_genres": top_genres,
            "platforms": target_platforms,
            "review_count": len(seen_game_ids),
        },
        "by_taste": by_taste,
        "by_platform": by_platform,
        "hidden_gems": hidden,
        "trending": trending,
    }


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------
@api.get("/games/top")
async def top_games(limit: int = 100, genre: Optional[str] = None, platform: Optional[str] = None):
    """Top games using ONLY real on-site reviews (no IGDB inflation).
    Bayesian-weighted score: (n*R + C*M) / (n + C)
      n = on-site review count, R = avg of `review.score` (0-10),
      C = prior weight (5), M = prior mean (7).
    Games with 0 reviews still appear (score = M = 7) but with site_review_count = 0.
    """
    flt = {}
    if genre: flt["genres"] = genre
    if platform: flt["platforms"] = platform

    C = 5.0
    M = 7.0

    review_pipeline = [
        {"$group": {"_id": "$game_id", "n": {"$sum": 1}, "avg": {"$avg": "$score"}}},
    ]
    review_stats = {}
    async for d in db.reviews.aggregate(review_pipeline):
        review_stats[d["_id"]] = (d["n"] or 0, d["avg"] or 0.0)

    cur = db.games.find(flt, {"_id": 0})
    games = []
    async for g in cur:
        n, R = review_stats.get(g["game_id"], (0, 0.0))
        score = (n * R + C * M) / (n + C)
        g["site_review_count"] = n
        g["site_avg_score"] = round(R, 2) if n > 0 else None
        g["bayesian_score"] = round(score, 2)
        games.append(g)

    games.sort(key=lambda x: (-x["bayesian_score"], -x["site_review_count"]))
    return games[: int(limit)]


@api.get("/games")
async def list_games(q: Optional[str] = None, genre: Optional[str] = None, platform: Optional[str] = None, limit: int = 200):
    flt = {}
    if q:
        flt["title"] = {"$regex": q, "$options": "i"}
    if genre:
        flt["genres"] = genre
    if platform:
        flt["platforms"] = platform
    cur = db.games.find(flt, {"_id": 0}).limit(limit)
    return await cur.to_list(limit)


@api.get("/games/meta")
async def games_meta():
    """Aggregate available genres and platforms from current catalog."""
    pipe_g = [{"$unwind": "$genres"}, {"$group": {"_id": "$genres", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]
    pipe_p = [{"$unwind": "$platforms"}, {"$group": {"_id": "$platforms", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]
    genres = [{"name": d["_id"], "count": d["n"]} async for d in db.games.aggregate(pipe_g)]
    platforms = [{"id": d["_id"], "count": d["n"]} async for d in db.games.aggregate(pipe_p)]
    total = await db.games.count_documents({})
    return {"genres": genres, "platforms": platforms, "total": total}


@api.get("/games/featured")
async def featured_games():
    """Return curated sections for homepage based on whatever's in DB."""
    async def top_by(query, sort_field, n):
        cur = db.games.find(query, {"_id": 0}).sort(sort_field, -1).limit(n)
        return [d async for d in cur]

    famous = await top_by({"rating": {"$gte": 80}}, "rating", 12)
    if not famous:
        famous = await top_by({}, "year", 12)
    horror = await top_by({"genres": {"$in": ["Terror", "Horror"]}}, "rating", 8)
    if not horror:
        horror = await top_by({"genres": "Aventura"}, "rating", 8)
    recent_titles = await top_by({"year": {"$gte": 2022}}, "year", 10)
    you_may_like = famous[:8]

    # Recent reviews
    rev_cur = db.reviews.find({}, {"_id": 0}).sort("created_at", -1).limit(10)
    recent_reviews = []
    async for r in rev_cur:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        if isinstance(r.get("updated_at"), datetime):
            r["updated_at"] = r["updated_at"].isoformat()
        g = await db.games.find_one({"game_id": r["game_id"]}, {"_id": 0, "title": 1, "cover": 1})
        if g:
            r["game_title"] = g["title"]
            r["game_cover"] = g["cover"]
        recent_reviews.append(r)

    return {
        "you_may_like": you_may_like,
        "famous": famous[:8],
        "horror": horror,
        "recent_titles": recent_titles,
        "recent_reviews": recent_reviews,
    }


@api.get("/games/{game_id}")
async def get_game(game_id: str):
    g = await db.games.find_one({"game_id": game_id}, {"_id": 0})
    if not g:
        raise HTTPException(404, "Jogo não encontrado")
    pipe = [
        {"$match": {"game_id": game_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$score"}, "count": {"$sum": 1}}},
    ]
    agg = await db.reviews.aggregate(pipe).to_list(1)
    g["avg_rating"] = round(agg[0]["avg"], 1) if agg and agg[0]["avg"] is not None else None
    g["review_count"] = agg[0]["count"] if agg else 0
    return g


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
REVIEW_CATEGORIES = ("graphics", "story", "tutorial", "gameplay", "audio", "performance", "fun")


def _is_review_complete(r: ReviewIn) -> bool:
    cat_values = [getattr(r, c) for c in REVIEW_CATEGORIES]
    return all([
        r.rating is not None,
        r.hours_played is not None,
        all(v is not None for v in cat_values),
        r.recommends is not None,
        r.platform,
        r.note and len(r.note.strip()) >= 10,
    ])


def _review_score(payload: ReviewIn) -> float:
    """Final user score = average of (overall rating, mean of filled categories)."""
    cat_values = [getattr(payload, c) for c in REVIEW_CATEGORIES if getattr(payload, c) is not None]
    if cat_values:
        cat_avg = sum(cat_values) / len(cat_values)
        return round((payload.rating + cat_avg) / 2, 2)
    return float(payload.rating)


@api.get("/games/{game_id}/reviews")
async def list_reviews(game_id: str):
    cur = db.reviews.find({"game_id": game_id}, {"_id": 0}).sort("created_at", -1)
    out = []
    async for r in cur:
        for k in ("created_at", "updated_at"):
            if isinstance(r.get(k), datetime):
                r[k] = r[k].isoformat()
        out.append(r)
    return out


@api.post("/games/{game_id}/reviews")
async def create_review(game_id: str, payload: ReviewIn, user: dict = Depends(get_verified_user)):
    g = await db.games.find_one({"game_id": game_id})
    if not g:
        raise HTTPException(404, "Jogo não encontrado")
    existing = await db.reviews.find_one({"game_id": game_id, "user_id": user["user_id"]})
    is_complete = _is_review_complete(payload)
    score = _review_score(payload)
    now = datetime.now(timezone.utc)
    if existing:
        was_complete = bool(existing.get("is_complete"))
        await db.reviews.update_one(
            {"review_id": existing["review_id"]},
            {"$set": {**payload.model_dump(), "is_complete": is_complete, "score": score, "updated_at": now.isoformat()}},
        )
        review_id = existing["review_id"]
        # Award the diff if user upgraded incomplete → complete
        if is_complete and not was_complete:
            await award_points(user["user_id"], 25)
    else:
        review_id = f"rev_{uuid.uuid4().hex[:12]}"
        doc = {
            "review_id": review_id,
            "game_id": game_id,
            "user_id": user["user_id"],
            "user_name": user.get("name"),
            "user_picture": user.get("picture"),
            **payload.model_dump(),
            "is_complete": is_complete,
            "score": score,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        await db.reviews.insert_one(doc)
        pts = 50 if is_complete else 25
        await award_points(user["user_id"], pts)
    r = await db.reviews.find_one({"review_id": review_id}, {"_id": 0})
    return r


@api.delete("/reviews/{review_id}")
async def delete_review(review_id: str, user: dict = Depends(get_verified_user)):
    r = await db.reviews.find_one({"review_id": review_id})
    if not r:
        raise HTTPException(404, "Avaliação não encontrada")
    if r["user_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.reviews.delete_one({"review_id": review_id})
    return {"ok": True}


@api.patch("/reviews/{review_id}")
async def update_review(review_id: str, payload: ReviewIn, user: dict = Depends(get_verified_user)):
    r = await db.reviews.find_one({"review_id": review_id})
    if not r:
        raise HTTPException(404, "Avaliação não encontrada")
    if r["user_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    was_complete = bool(r.get("is_complete"))
    is_complete = _is_review_complete(payload)
    score = _review_score(payload)
    await db.reviews.update_one(
        {"review_id": review_id},
        {"$set": {**payload.model_dump(), "is_complete": is_complete, "score": score, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Award diff if upgraded from partial → complete
    if is_complete and not was_complete and r["user_id"] == user["user_id"]:
        await award_points(user["user_id"], 25)
    return await db.reviews.find_one({"review_id": review_id}, {"_id": 0})


@api.get("/users/{user_id}/reviews")
async def user_reviews(user_id: str):
    cur = db.reviews.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    out = []
    async for r in cur:
        for k in ("created_at", "updated_at"):
            if isinstance(r.get(k), datetime):
                r[k] = r[k].isoformat()
        g = await db.games.find_one({"game_id": r["game_id"]}, {"_id": 0, "title": 1, "cover": 1})
        if g:
            r["game_title"] = g["title"]
            r["game_cover"] = g["cover"]
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Guides — Explorador+ (50pts) only
# ---------------------------------------------------------------------------
@api.get("/games/{game_id}/guides")
async def list_guides(game_id: str):
    cur = db.guides.find({"game_id": game_id}, {"_id": 0}).sort("created_at", -1)
    out = []
    async for d in cur:
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out


@api.post("/games/{game_id}/guides")
async def create_guide(game_id: str, payload: GuideIn, user: dict = Depends(get_verified_user)):
    if user.get("points", 0) < 50:
        raise HTTPException(403, "Precisa do nível Explorador (50 pts) para criar guias")
    g = await db.games.find_one({"game_id": game_id})
    if not g:
        raise HTTPException(404, "Jogo não encontrado")
    guide_id = f"gd_{uuid.uuid4().hex[:12]}"
    doc = {
        "guide_id": guide_id,
        "game_id": game_id,
        "author_id": user["user_id"],
        "author_name": user.get("name"),
        "author_picture": user.get("picture"),
        "title": payload.title,
        "content": payload.content,
        "category": payload.category,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.guides.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/guides/{guide_id}")
async def delete_guide(guide_id: str, user: dict = Depends(get_verified_user)):
    g = await db.guides.find_one({"guide_id": guide_id})
    if not g:
        raise HTTPException(404, "Guia não encontrado")
    if g["author_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.guides.delete_one({"guide_id": guide_id})
    return {"ok": True}


@api.patch("/guides/{guide_id}")
async def update_guide(guide_id: str, payload: GuideIn, user: dict = Depends(get_verified_user)):
    g = await db.guides.find_one({"guide_id": guide_id})
    if not g:
        raise HTTPException(404, "Guia não encontrado")
    if g["author_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.guides.update_one(
        {"guide_id": guide_id},
        {"$set": {**payload.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return await db.guides.find_one({"guide_id": guide_id}, {"_id": 0})


@api.patch("/help-requests/{help_id}")
async def update_help(help_id: str, payload: HelpRequestIn, user: dict = Depends(get_verified_user)):
    h = await db.help_requests.find_one({"help_id": help_id})
    if not h:
        raise HTTPException(404, "Pedido não encontrado")
    if h["author_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.help_requests.update_one(
        {"help_id": help_id},
        {"$set": {**payload.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return await db.help_requests.find_one({"help_id": help_id}, {"_id": 0})


@api.delete("/help-requests/{help_id}")
async def delete_help(help_id: str, user: dict = Depends(get_verified_user)):
    h = await db.help_requests.find_one({"help_id": help_id})
    if not h:
        raise HTTPException(404, "Pedido não encontrado")
    if h["author_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.help_requests.delete_one({"help_id": help_id})
    return {"ok": True}


@api.patch("/help-requests/{help_id}/replies/{reply_id}")
async def update_reply(help_id: str, reply_id: str, payload: HelpReplyIn, user: dict = Depends(get_verified_user)):
    h = await db.help_requests.find_one({"help_id": help_id, "replies.reply_id": reply_id})
    if not h:
        raise HTTPException(404, "Resposta não encontrada")
    reply = next((r for r in h.get("replies", []) if r.get("reply_id") == reply_id), None)
    if not reply:
        raise HTTPException(404, "Resposta não encontrada")
    if reply.get("author_id") != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.help_requests.update_one(
        {"help_id": help_id, "replies.reply_id": reply_id},
        {"$set": {"replies.$.content": payload.content, "replies.$.updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}


@api.delete("/help-requests/{help_id}/replies/{reply_id}")
async def delete_reply(help_id: str, reply_id: str, user: dict = Depends(get_verified_user)):
    h = await db.help_requests.find_one({"help_id": help_id, "replies.reply_id": reply_id})
    if not h:
        raise HTTPException(404, "Resposta não encontrada")
    reply = next((r for r in h.get("replies", []) if r.get("reply_id") == reply_id), None)
    if not reply:
        raise HTTPException(404, "Resposta não encontrada")
    if reply.get("author_id") != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.help_requests.update_one(
        {"help_id": help_id},
        {"$pull": {"replies": {"reply_id": reply_id}}},
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Help requests
# ---------------------------------------------------------------------------
@api.get("/help-requests")
async def list_help(kind: Optional[str] = None, game_id: Optional[str] = None, limit: int = 50):
    flt = {}
    if kind: flt["kind"] = kind
    if game_id: flt["game_id"] = game_id
    cur = db.help_requests.find(flt, {"_id": 0}).sort("created_at", -1).limit(limit)
    out = []
    async for d in cur:
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out


@api.post("/help-requests")
async def create_help(payload: HelpRequestIn, user: dict = Depends(get_verified_user)):
    hid = f"hr_{uuid.uuid4().hex[:12]}"
    doc = {
        "help_id": hid,
        "title": payload.title,
        "content": payload.content,
        "kind": payload.kind,
        "game_id": payload.game_id,
        "author_id": user["user_id"],
        "author_name": user.get("name"),
        "author_picture": user.get("picture"),
        "replies": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.help_requests.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.post("/help-requests/{help_id}/replies")
async def reply_help(help_id: str, payload: HelpReplyIn, user: dict = Depends(get_verified_user)):
    h = await db.help_requests.find_one({"help_id": help_id})
    if not h:
        raise HTTPException(404, "Pedido não encontrado")
    reply = {
        "reply_id": f"rp_{uuid.uuid4().hex[:8]}",
        "author_id": user["user_id"],
        "author_name": user.get("name"),
        "author_picture": user.get("picture"),
        "content": payload.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.help_requests.update_one({"help_id": help_id}, {"$push": {"replies": reply}})
    return reply


# ---------------------------------------------------------------------------
# Friends + Chat (simple)
# ---------------------------------------------------------------------------
@api.get("/friends")
async def list_friends(user: dict = Depends(get_verified_user)):
    cur = db.friendships.find({"$or": [{"from_user": user["user_id"], "status": "accepted"}, {"to_user": user["user_id"], "status": "accepted"}]}, {"_id": 0})
    friends = []
    async for f in cur:
        other_id = f["to_user"] if f["from_user"] == user["user_id"] else f["from_user"]
        u = await db.users.find_one({"user_id": other_id}, {"_id": 0, "password_hash": 0, "email": 0})
        if u:
            friends.append(public_user(u))
    return friends


@api.get("/friends/requests")
async def friend_requests(user: dict = Depends(get_current_user)):
    cur = db.friendships.find({"to_user": user["user_id"], "status": "pending"}, {"_id": 0})
    out = []
    async for f in cur:
        u = await db.users.find_one({"user_id": f["from_user"]}, {"_id": 0, "password_hash": 0, "email": 0})
        if u:
            out.append({"from_user": public_user(u), "created_at": f.get("created_at")})
    return out


@api.post("/friends/request/{user_id}")
async def send_friend_request(user_id: str, user: dict = Depends(get_verified_user)):
    if user_id == user["user_id"]:
        raise HTTPException(400, "Não pode adicionar-se a si mesmo")
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(404, "Utilizador não encontrado")
    existing = await db.friendships.find_one({"$or": [
        {"from_user": user["user_id"], "to_user": user_id},
        {"from_user": user_id, "to_user": user["user_id"]},
    ]})
    if existing:
        raise HTTPException(400, "Pedido já existe")
    await db.friendships.insert_one({
        "from_user": user["user_id"],
        "to_user": user_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


@api.post("/friends/accept/{user_id}")
async def accept_friend(user_id: str, user: dict = Depends(get_verified_user)):
    res = await db.friendships.update_one(
        {"from_user": user_id, "to_user": user["user_id"], "status": "pending"},
        {"$set": {"status": "accepted"}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Pedido não encontrado")
    return {"ok": True}


@api.delete("/friends/{user_id}")
async def remove_friendship(user_id: str, user: dict = Depends(get_verified_user)):
    """Remove a friendship (accepted) or cancel a pending request, in either direction."""
    res = await db.friendships.delete_one({
        "$or": [
            {"from_user": user["user_id"], "to_user": user_id},
            {"from_user": user_id, "to_user": user["user_id"]},
        ]
    })
    if res.deleted_count == 0:
        raise HTTPException(404, "Amizade não encontrada")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Chat — Direct Messages (between friends) + Communities (public groups)
# ---------------------------------------------------------------------------
class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class CommunityIn(BaseModel):
    name: str = Field(min_length=3, max_length=40)
    description: Optional[str] = Field(default="", max_length=240)
    icon: Optional[str] = None


def _dm_key(a: str, b: str) -> str:
    return "dm::" + "::".join(sorted([a, b]))


async def _are_friends(a: str, b: str) -> bool:
    f = await db.friendships.find_one({
        "$or": [
            {"from_user": a, "to_user": b, "status": "accepted"},
            {"from_user": b, "to_user": a, "status": "accepted"},
        ]
    })
    return bool(f)


@api.get("/chat/threads")
async def list_chat_threads(user: dict = Depends(get_verified_user)):
    """Return DM threads (one per friend with whom we've exchanged at least 1 message,
    plus all accepted friends so the user can start chatting)."""
    me = user["user_id"]
    # All accepted friends
    friends_cur = db.friendships.find(
        {"$or": [{"from_user": me, "status": "accepted"}, {"to_user": me, "status": "accepted"}]},
        {"_id": 0},
    )
    friend_ids = []
    async for f in friends_cur:
        friend_ids.append(f["to_user"] if f["from_user"] == me else f["from_user"])
    if not friend_ids:
        return []
    # Latest message per thread
    keys = [_dm_key(me, fid) for fid in friend_ids]
    latest = {}
    pipe = [
        {"$match": {"thread_key": {"$in": keys}}},
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$thread_key", "last": {"$first": "$$ROOT"}}},
    ]
    async for d in db.messages.aggregate(pipe):
        latest[d["_id"]] = d["last"]
    # Build response
    users = {u["user_id"]: u async for u in db.users.find({"user_id": {"$in": friend_ids}}, {"_id": 0, "user_id": 1, "name": 1, "picture": 1})}
    threads = []
    for fid in friend_ids:
        u = users.get(fid)
        if not u:
            continue
        last = latest.get(_dm_key(me, fid))
        threads.append({
            "user_id": fid,
            "name": u.get("name"),
            "picture": u.get("picture"),
            "last_message": last.get("content") if last else None,
            "last_at": last.get("created_at") if last else None,
            "last_sender": last.get("sender_id") if last else None,
        })
    threads.sort(key=lambda t: (t["last_at"] or "", t["name"] or ""), reverse=True)
    return threads


@api.get("/chat/dm/{user_id}")
async def get_dm_messages(user_id: str, after: Optional[str] = None, user: dict = Depends(get_current_user)):
    me = user["user_id"]
    if me == user_id:
        raise HTTPException(400, "Não podes conversar contigo próprio")
    if not await _are_friends(me, user_id):
        raise HTTPException(403, "Só podes conversar com amigos")
    flt = {"thread_key": _dm_key(me, user_id)}
    if after:
        flt["created_at"] = {"$gt": after}
    cur = db.messages.find(flt, {"_id": 0}).sort("created_at", 1).limit(500)
    return [m async for m in cur]


@api.post("/chat/dm/{user_id}")
async def send_dm(user_id: str, payload: MessageIn, user: dict = Depends(get_verified_user)):
    me = user["user_id"]
    if me == user_id:
        raise HTTPException(400, "Não podes conversar contigo próprio")
    if not await _are_friends(me, user_id):
        raise HTTPException(403, "Só podes enviar mensagens a amigos")
    msg = {
        "msg_id": f"msg_{uuid.uuid4().hex[:12]}",
        "thread_key": _dm_key(me, user_id),
        "type": "dm",
        "sender_id": me,
        "sender_name": user.get("name"),
        "sender_picture": user.get("picture"),
        "content": payload.content.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.messages.insert_one(msg)
    msg.pop("_id", None)
    return msg


@api.get("/communities")
async def list_communities(q: Optional[str] = None, user: dict = Depends(get_current_user_optional)):
    flt = {}
    if q:
        flt["name"] = {"$regex": q, "$options": "i"}
    cur = db.communities.find(flt, {"_id": 0}).sort("members_count", -1).limit(200)
    out = []
    me_id = user["user_id"] if user else None
    async for c in cur:
        c["is_member"] = bool(me_id and me_id in (c.get("members") or []))
        c["members_count"] = len(c.get("members") or [])
        c.pop("members", None)
        out.append(c)
    return out


@api.post("/communities")
async def create_community(payload: CommunityIn, user: dict = Depends(get_verified_user)):
    cid = f"com_{uuid.uuid4().hex[:10]}"
    doc = {
        "community_id": cid,
        "name": payload.name.strip(),
        "description": (payload.description or "").strip(),
        "icon": payload.icon,
        "owner_id": user["user_id"],
        "members": [user["user_id"]],
        "members_count": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.communities.insert_one(doc)
    doc.pop("_id", None)
    doc["is_member"] = True
    doc.pop("members", None)
    return doc


@api.post("/communities/{community_id}/join")
async def join_community(community_id: str, user: dict = Depends(get_verified_user)):
    res = await db.communities.update_one(
        {"community_id": community_id},
        {"$addToSet": {"members": user["user_id"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Comunidade não encontrada")
    # Recount
    c = await db.communities.find_one({"community_id": community_id}, {"_id": 0, "members": 1})
    await db.communities.update_one({"community_id": community_id}, {"$set": {"members_count": len(c.get("members") or [])}})
    return {"ok": True}


@api.delete("/communities/{community_id}/leave")
async def leave_community(community_id: str, user: dict = Depends(get_verified_user)):
    res = await db.communities.update_one(
        {"community_id": community_id},
        {"$pull": {"members": user["user_id"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Comunidade não encontrada")
    c = await db.communities.find_one({"community_id": community_id}, {"_id": 0, "members": 1})
    await db.communities.update_one({"community_id": community_id}, {"$set": {"members_count": len(c.get("members") or [])}})
    return {"ok": True}


@api.get("/communities/{community_id}")
async def get_community(community_id: str, user: dict = Depends(get_current_user_optional)):
    c = await db.communities.find_one({"community_id": community_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Comunidade não encontrada")
    me_id = user["user_id"] if user else None
    c["is_member"] = bool(me_id and me_id in (c.get("members") or []))
    c["members_count"] = len(c.get("members") or [])
    c.pop("members", None)
    return c


@api.get("/communities/{community_id}/messages")
async def get_community_messages(community_id: str, after: Optional[str] = None, user: dict = Depends(get_verified_user)):
    c = await db.communities.find_one({"community_id": community_id}, {"_id": 0, "members": 1})
    if not c:
        raise HTTPException(404, "Comunidade não encontrada")
    if user["user_id"] not in (c.get("members") or []):
        raise HTTPException(403, "Junta-te à comunidade para ver mensagens")
    flt = {"thread_key": f"com::{community_id}"}
    if after:
        flt["created_at"] = {"$gt": after}
    cur = db.messages.find(flt, {"_id": 0}).sort("created_at", 1).limit(500)
    return [m async for m in cur]


@api.post("/communities/{community_id}/messages")
async def post_community_message(community_id: str, payload: MessageIn, user: dict = Depends(get_verified_user)):
    c = await db.communities.find_one({"community_id": community_id}, {"_id": 0, "members": 1})
    if not c:
        raise HTTPException(404, "Comunidade não encontrada")
    if user["user_id"] not in (c.get("members") or []):
        raise HTTPException(403, "Junta-te à comunidade para enviar mensagens")
    msg = {
        "msg_id": f"msg_{uuid.uuid4().hex[:12]}",
        "thread_key": f"com::{community_id}",
        "type": "community",
        "community_id": community_id,
        "sender_id": user["user_id"],
        "sender_name": user.get("name"),
        "sender_picture": user.get("picture"),
        "content": payload.content.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.messages.insert_one(msg)
    msg.pop("_id", None)
    return msg


@api.delete("/chat/messages/{msg_id}")
async def delete_dm_message(msg_id: str, user: dict = Depends(get_verified_user)):
    """Delete a DM message — sender or admin only."""
    m = await db.messages.find_one({"msg_id": msg_id, "type": "dm"})
    if not m:
        raise HTTPException(404, "Mensagem não encontrada")
    if m["sender_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.messages.delete_one({"msg_id": msg_id})
    return {"ok": True}


@api.delete("/communities/{community_id}/messages/{msg_id}")
async def delete_community_message(community_id: str, msg_id: str, user: dict = Depends(get_current_user)):
    """Delete a community message — sender, community owner or admin only."""
    m = await db.messages.find_one({"msg_id": msg_id, "type": "community", "community_id": community_id})
    if not m:
        raise HTTPException(404, "Mensagem não encontrada")
    c = await db.communities.find_one({"community_id": community_id}, {"_id": 0, "owner_id": 1})
    is_owner = c and c.get("owner_id") == user["user_id"]
    if m["sender_id"] != user["user_id"] and not is_owner and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.messages.delete_one({"msg_id": msg_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin moderation
# ---------------------------------------------------------------------------
def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas administradores")
    return user


class GamePatchIn(BaseModel):
    title: Optional[str] = None
    cover: Optional[str] = None
    description: Optional[str] = None
    year: Optional[int] = None
    genres: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    developer: Optional[str] = None


class SuspendIn(BaseModel):
    days: int = Field(default=7, ge=1, le=365)
    reason: Optional[str] = ""


class WarnIn(BaseModel):
    message: str = Field(min_length=2, max_length=400)


@api.get("/admin/users")
async def admin_list_users(q: Optional[str] = None, _: dict = Depends(require_admin)):
    flt = {}
    if q:
        flt = {"$or": [
            {"email": {"$regex": q, "$options": "i"}},
            {"name": {"$regex": q, "$options": "i"}},
            {"user_id": {"$regex": q, "$options": "i"}},
        ]}
    cur = db.users.find(flt, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(200)
    out = []
    async for u in cur:
        if isinstance(u.get("created_at"), datetime):
            u["created_at"] = u["created_at"].isoformat()
        out.append(u)
    return out


@api.post("/admin/users/{user_id}/suspend")
async def admin_suspend(user_id: str, payload: SuspendIn, admin: dict = Depends(require_admin)):
    until = datetime.now(timezone.utc) + timedelta(days=payload.days)
    res = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "suspended_until": until.isoformat(),
            "suspended_reason": payload.reason or "",
            "suspended_by": admin["user_id"],
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Utilizador não encontrado")
    return {"ok": True, "until": until.isoformat()}


@api.post("/admin/users/{user_id}/unsuspend")
async def admin_unsuspend(user_id: str, _: dict = Depends(require_admin)):
    res = await db.users.update_one(
        {"user_id": user_id},
        {"$unset": {"suspended_until": "", "suspended_reason": "", "suspended_by": ""}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Utilizador não encontrado")
    return {"ok": True}


@api.post("/admin/users/{user_id}/warn")
async def admin_warn(user_id: str, payload: WarnIn, admin: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1})
    if not target:
        raise HTTPException(404, "Utilizador não encontrado")
    warning = {
        "warning_id": f"warn_{uuid.uuid4().hex[:10]}",
        "user_id": user_id,
        "message": payload.message,
        "by": admin["user_id"],
        "by_name": admin.get("name"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.warnings.insert_one(warning)
    warning.pop("_id", None)
    return warning


@api.get("/admin/warnings")
async def admin_warnings(user_id: Optional[str] = None, _: dict = Depends(require_admin)):
    flt = {"user_id": user_id} if user_id else {}
    cur = db.warnings.find(flt, {"_id": 0}).sort("created_at", -1).limit(200)
    return [w async for w in cur]


@api.get("/users/me/warnings")
async def my_warnings(user: dict = Depends(get_current_user)):
    cur = db.warnings.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1)
    return [w async for w in cur]


@api.patch("/admin/games/{game_id}")
async def admin_edit_game(game_id: str, payload: GamePatchIn, _: dict = Depends(require_admin)):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "Nada para atualizar")
    res = await db.games.update_one({"game_id": game_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Jogo não encontrado")
    return await db.games.find_one({"game_id": game_id}, {"_id": 0})


@api.post("/admin/reviews/{review_id}/feature")
async def admin_feature_review(review_id: str, _: dict = Depends(require_admin)):
    res = await db.reviews.update_one({"review_id": review_id}, {"$set": {"featured": True, "featured_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Avaliação não encontrada")
    return {"ok": True}


@api.delete("/admin/reviews/{review_id}/feature")
async def admin_unfeature_review(review_id: str, _: dict = Depends(require_admin)):
    res = await db.reviews.update_one({"review_id": review_id}, {"$unset": {"featured": "", "featured_at": ""}})
    if res.matched_count == 0:
        raise HTTPException(404, "Avaliação não encontrada")
    return {"ok": True}


@api.post("/admin/guides/{guide_id}/feature")
async def admin_feature_guide(guide_id: str, _: dict = Depends(require_admin)):
    res = await db.guides.update_one({"guide_id": guide_id}, {"$set": {"featured": True, "featured_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Guia não encontrado")
    return {"ok": True}


@api.delete("/admin/guides/{guide_id}/feature")
async def admin_unfeature_guide(guide_id: str, _: dict = Depends(require_admin)):
    res = await db.guides.update_one({"guide_id": guide_id}, {"$unset": {"featured": "", "featured_at": ""}})
    if res.matched_count == 0:
        raise HTTPException(404, "Guia não encontrado")
    return {"ok": True}


@api.delete("/admin/messages/{msg_id}")
async def admin_delete_message(msg_id: str, _: dict = Depends(require_admin)):
    res = await db.messages.delete_one({"msg_id": msg_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Mensagem não encontrada")
    return {"ok": True}


@api.get("/admin/stats")
async def admin_stats(_: dict = Depends(require_admin)):
    return {
        "users": await db.users.count_documents({}),
        "games": await db.games.count_documents({}),
        "reviews": await db.reviews.count_documents({}),
        "guides": await db.guides.count_documents({}),
        "communities": await db.communities.count_documents({}),
        "messages": await db.messages.count_documents({}),
        "suspended_users": await db.users.count_documents({"suspended_until": {"$exists": True}}),
    }


# ---------------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------------
app.include_router(api)

frontend_url = os.environ.get("FRONTEND_URL", "*")
allowed = [u.strip() for u in frontend_url.split(",") if u.strip()] if frontend_url != "*" else []
# Allow any *.preview.emergentagent.com origin for dev/preview reachability
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_origin_regex=r"https?://([a-z0-9-]+\.)*emergentagent\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"app": "GameScout", "ok": True}
