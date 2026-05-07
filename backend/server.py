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

    # Seed admin
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
            "social": {},
            "prefs": {"platforms": ["pc"], "favorite_game": None, "pc_specs": None},
            "created_at": datetime.now(timezone.utc),
        })
        log.info("Admin seeded: %s", admin_email)
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})

    # Game catalog: import from IGDB on startup, then schedule periodic refresh
    asyncio.create_task(_refresh_games_catalog())
    asyncio.create_task(_periodic_refresh_loop())


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
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email já registado")
    user_id = gen_user_id()
    doc = {
        "user_id": user_id,
        "email": email,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
        "role": "user",
        "points": 0,
        "bio": "",
        "picture": None,
        "auth_provider": "email",
        "social": {},
        "prefs": {"platforms": [], "favorite_game": None, "favorite_game_id": None, "pc_specs": None},
        "created_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(doc)
    set_jwt_cookies(response, user_id)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return public_user(user)


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response, request: Request):
    email = payload.email.lower()
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
    return public_user(user)


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
    return public_user(user)


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

    user = await db.users.find_one({"email": email})
    if not user:
        user_id = gen_user_id()
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": "user",
            "points": 0,
            "bio": "",
            "auth_provider": "google",
            "social": {},
            "prefs": {"platforms": [], "favorite_game": None, "favorite_game_id": None, "pc_specs": None},
            "created_at": datetime.now(timezone.utc),
        })
        user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    else:
        if picture and not user.get("picture"):
            await db.users.update_one({"email": email}, {"$set": {"picture": picture}})
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
    return u


@api.patch("/users/me")
async def update_me(payload: ProfileUpdateIn, user: dict = Depends(get_current_user)):
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
async def upload_avatar(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
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
async def search_users(q: str = Query(min_length=2), user: dict = Depends(get_current_user)):
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
async def add_to_wishlist(game_id: str, user: dict = Depends(get_current_user)):
    g = await db.games.find_one({"game_id": game_id}, {"_id": 0, "game_id": 1})
    if not g:
        raise HTTPException(404, "Jogo não encontrado")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$addToSet": {"wishlist": game_id}},
    )
    return {"ok": True, "in_wishlist": True}


@api.delete("/wishlist/{game_id}")
async def remove_from_wishlist(game_id: str, user: dict = Depends(get_current_user)):
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
async def discover(user: dict = Depends(get_current_user)):
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
    """Top games using a Bayesian-weighted score (rating × confidence by review count).
    Formula: score = (n*R + C*M) / (n + C)
      n = rating_count (IGDB), R = rating (0-100), C = prior weight (50), M = prior mean (70).
    Returns games sorted by `bayesian_score` desc.
    """
    flt = {"rating_count": {"$gte": 5}}
    if genre: flt["genres"] = genre
    if platform: flt["platforms"] = platform
    C = 50.0
    M = 70.0
    pipeline = [
        {"$match": flt},
        {"$addFields": {
            "bayesian_score": {
                "$divide": [
                    {"$add": [
                        {"$multiply": ["$rating_count", "$rating"]},
                        C * M,
                    ]},
                    {"$add": ["$rating_count", C]},
                ]
            }
        }},
        {"$sort": {"bayesian_score": -1}},
        {"$limit": int(limit)},
        {"$project": {"_id": 0}},
    ]
    return [d async for d in db.games.aggregate(pipeline)]


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
    # rating aggregate
    pipe = [
        {"$match": {"game_id": game_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    agg = await db.reviews.aggregate(pipe).to_list(1)
    g["avg_rating"] = round(agg[0]["avg"], 1) if agg else None
    g["review_count"] = agg[0]["count"] if agg else 0
    return g


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
def _is_review_complete(r: ReviewIn) -> bool:
    return all([
        r.rating is not None,
        r.hours_played is not None,
        r.graphics is not None,
        r.story is not None,
        r.tutorial is not None,
        r.gameplay is not None,
        r.recommends is not None,
        r.platform,
        r.note and len(r.note.strip()) >= 10,
    ])


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
async def create_review(game_id: str, payload: ReviewIn, user: dict = Depends(get_current_user)):
    g = await db.games.find_one({"game_id": game_id})
    if not g:
        raise HTTPException(404, "Jogo não encontrado")
    existing = await db.reviews.find_one({"game_id": game_id, "user_id": user["user_id"]})
    is_complete = _is_review_complete(payload)
    now = datetime.now(timezone.utc)
    if existing:
        await db.reviews.update_one(
            {"review_id": existing["review_id"]},
            {"$set": {**payload.model_dump(), "is_complete": is_complete, "updated_at": now.isoformat()}},
        )
        review_id = existing["review_id"]
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
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        await db.reviews.insert_one(doc)
        pts = 50 if is_complete else 25
        await award_points(user["user_id"], pts)
    r = await db.reviews.find_one({"review_id": review_id}, {"_id": 0})
    return r


@api.delete("/reviews/{review_id}")
async def delete_review(review_id: str, user: dict = Depends(get_current_user)):
    r = await db.reviews.find_one({"review_id": review_id})
    if not r:
        raise HTTPException(404, "Avaliação não encontrada")
    if r["user_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.reviews.delete_one({"review_id": review_id})
    return {"ok": True}


@api.patch("/reviews/{review_id}")
async def update_review(review_id: str, payload: ReviewIn, user: dict = Depends(get_current_user)):
    r = await db.reviews.find_one({"review_id": review_id})
    if not r:
        raise HTTPException(404, "Avaliação não encontrada")
    if r["user_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    is_complete = _is_review_complete(payload)
    await db.reviews.update_one(
        {"review_id": review_id},
        {"$set": {**payload.model_dump(), "is_complete": is_complete, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
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
async def create_guide(game_id: str, payload: GuideIn, user: dict = Depends(get_current_user)):
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
async def delete_guide(guide_id: str, user: dict = Depends(get_current_user)):
    g = await db.guides.find_one({"guide_id": guide_id})
    if not g:
        raise HTTPException(404, "Guia não encontrado")
    if g["author_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.guides.delete_one({"guide_id": guide_id})
    return {"ok": True}


@api.patch("/guides/{guide_id}")
async def update_guide(guide_id: str, payload: GuideIn, user: dict = Depends(get_current_user)):
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
async def update_help(help_id: str, payload: HelpRequestIn, user: dict = Depends(get_current_user)):
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
async def delete_help(help_id: str, user: dict = Depends(get_current_user)):
    h = await db.help_requests.find_one({"help_id": help_id})
    if not h:
        raise HTTPException(404, "Pedido não encontrado")
    if h["author_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Sem permissão")
    await db.help_requests.delete_one({"help_id": help_id})
    return {"ok": True}


@api.patch("/help-requests/{help_id}/replies/{reply_id}")
async def update_reply(help_id: str, reply_id: str, payload: HelpReplyIn, user: dict = Depends(get_current_user)):
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
async def delete_reply(help_id: str, reply_id: str, user: dict = Depends(get_current_user)):
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
async def create_help(payload: HelpRequestIn, user: dict = Depends(get_current_user)):
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
async def reply_help(help_id: str, payload: HelpReplyIn, user: dict = Depends(get_current_user)):
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
async def list_friends(user: dict = Depends(get_current_user)):
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
async def send_friend_request(user_id: str, user: dict = Depends(get_current_user)):
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
async def accept_friend(user_id: str, user: dict = Depends(get_current_user)):
    res = await db.friendships.update_one(
        {"from_user": user_id, "to_user": user["user_id"], "status": "pending"},
        {"$set": {"status": "accepted"}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Pedido não encontrado")
    return {"ok": True}


@api.delete("/friends/{user_id}")
async def remove_friendship(user_id: str, user: dict = Depends(get_current_user)):
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
