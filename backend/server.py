"""GameScout backend - FastAPI + MongoDB.
Auth: dual flow (JWT email/password + Emergent Google session_token).
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
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


@app.on_event("startup")
async def startup():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.games.create_index("game_id", unique=True)
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
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
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

    # Seed games
    for g in GAMES_SEED:
        await db.games.update_one({"game_id": g["game_id"]}, {"$setOnInsert": g}, upsert=True)
    log.info("Games seeded: %d", await db.games.count_documents({}))


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
    user_id = f"user_{uuid.uuid4().hex[:12]}"
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
        "prefs": {"platforms": [], "favorite_game": None, "pc_specs": None},
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
        user_id = f"user_{uuid.uuid4().hex[:12]}"
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
            "prefs": {"platforms": [], "favorite_game": None, "pc_specs": None},
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
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    out = public_user(fresh)
    out["rank"] = rank_for_points(out.get("points", 0))
    return out


@api.get("/users/search")
async def search_users(q: str = Query(min_length=2), user: dict = Depends(get_current_user)):
    cur = db.users.find(
        {"name": {"$regex": q, "$options": "i"}, "user_id": {"$ne": user["user_id"]}},
        {"_id": 0, "password_hash": 0, "email": 0},
    ).limit(20)
    return [public_user(u) async for u in cur]


@api.get("/users/{user_id}")
async def get_user_public(user_id: str):
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0, "email": 0})
    if not u:
        raise HTTPException(404, "Utilizador não encontrado")
    out = public_user(u)
    out["rank"] = rank_for_points(out.get("points", 0))
    review_count = await db.reviews.count_documents({"user_id": user_id})
    guide_count = await db.guides.count_documents({"author_id": user_id})
    out["stats"] = {"reviews": review_count, "guides": guide_count}
    return out


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------
@api.get("/games")
async def list_games(q: Optional[str] = None, genre: Optional[str] = None, platform: Optional[str] = None, limit: int = 60):
    flt = {}
    if q:
        flt["title"] = {"$regex": q, "$options": "i"}
    if genre:
        flt["genres"] = genre
    if platform:
        flt["platforms"] = platform
    cur = db.games.find(flt, {"_id": 0}).limit(limit)
    return await cur.to_list(limit)


@api.get("/games/featured")
async def featured_games():
    """Return curated sections for homepage."""
    famous_ids = ["zelda-totk", "elden-ring", "gta-v", "minecraft", "rdr2", "witcher-3"]
    horror_ids = ["resident-evil-4-r", "silent-hill-2-r", "alan-wake-2", "phasmophobia"]
    recent_ids = ["bg3", "spider-man-2", "hogwarts-legacy", "totk", "ff16"]

    async def by_ids(ids):
        out = []
        cur = db.games.find({"game_id": {"$in": ids}}, {"_id": 0})
        async for d in cur:
            out.append(d)
        return out

    famous = await by_ids(famous_ids)
    horror = await by_ids(horror_ids)
    recent_titles = await by_ids(recent_ids)

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
        "you_may_like": famous,
        "famous": famous,
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


class HelpReplyIn(BaseModel):
    content: str = Field(min_length=2)


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


# ---------------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------------
app.include_router(api)

frontend_url = os.environ.get("FRONTEND_URL", "*")
allowed = [frontend_url] if frontend_url != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"app": "GameScout", "ok": True}
