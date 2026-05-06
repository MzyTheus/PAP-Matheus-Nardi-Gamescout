"""IGDB importer — fetches popular + recent games from IGDB via Twitch OAuth.

Auth: POST https://id.twitch.tv/oauth2/token (client_credentials)
Games: POST https://api.igdb.com/v4/games (text body, IGDB query language)
Cover: https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg
"""
from __future__ import annotations
import os
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

import requests

log = logging.getLogger("igdb")

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_GAMES_URL = "https://api.igdb.com/v4/games"

# IGDB platform name → our internal id
PLATFORM_MAP = {
    "PC (Microsoft Windows)": "pc",
    "Mac": "pc",
    "Linux": "pc",
    "PlayStation 5": "ps5",
    "PlayStation 4": "ps4",
    "PlayStation 3": "ps3",
    "Xbox Series X|S": "xbox-series-x",
    "Xbox One": "xbox-one",
    "Xbox 360": "xbox-360",
    "Nintendo Switch": "switch",
    "Nintendo Switch 2": "switch",
    "iOS": "mobile",
    "Android": "mobile",
}

# IGDB genre → PT label
GENRE_MAP = {
    "Adventure": "Aventura",
    "Role-playing (RPG)": "RPG",
    "Shooter": "FPS",
    "Strategy": "Estratégia",
    "Sport": "Desporto",
    "Racing": "Corridas",
    "Simulator": "Simulação",
    "Fighting": "Luta",
    "Platform": "Plataformas",
    "Puzzle": "Puzzle",
    "Indie": "Indie",
    "Arcade": "Arcade",
    "Tactical": "Tático",
    "Music": "Musical",
    "Real Time Strategy (RTS)": "RTS",
    "Turn-based strategy (TBS)": "Estratégia",
    "Card & Board Game": "Cartas",
    "MOBA": "MOBA",
    "Hack and slash/Beat 'em up": "Ação",
    "Quiz/Trivia": "Quiz",
    "Pinball": "Pinball",
    "Visual Novel": "Novela Visual",
    "Point-and-click": "Aventura",
}


def _get_token(client_id: str, client_secret: str) -> str:
    r = requests.post(
        TWITCH_TOKEN_URL,
        params={"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _query(client_id: str, token: str, body: str) -> List[Dict[str, Any]]:
    r = requests.post(
        IGDB_GAMES_URL,
        headers={"Client-ID": client_id, "Authorization": f"Bearer {token}", "Content-Type": "text/plain"},
        data=body,
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _normalise(item: Dict[str, Any]) -> Dict[str, Any] | None:
    cover = item.get("cover") or {}
    image_id = cover.get("image_id")
    if not image_id:
        return None

    platforms_raw = item.get("platforms") or []
    platform_ids = []
    for p in platforms_raw:
        mapped = PLATFORM_MAP.get(p.get("name") or "")
        if mapped and mapped not in platform_ids:
            platform_ids.append(mapped)
    if not platform_ids:
        return None

    genres_raw = item.get("genres") or []
    genres = []
    for g in genres_raw:
        gn = g.get("name") or ""
        gn = GENRE_MAP.get(gn, gn)
        if gn and gn not in genres:
            genres.append(gn)

    # Year
    year = None
    ts = item.get("first_release_date")
    if ts:
        try:
            year = datetime.fromtimestamp(int(ts), tz=timezone.utc).year
        except Exception:
            year = None

    # Developer (involved_companies where developer=true)
    developer = None
    for ic in (item.get("involved_companies") or []):
        if ic.get("developer"):
            company = ic.get("company") or {}
            developer = company.get("name")
            if developer:
                break
    if not developer:
        for ic in (item.get("involved_companies") or []):
            company = ic.get("company") or {}
            if company.get("name"):
                developer = company["name"]
                break
    developer = developer or "Unknown"

    return {
        "game_id": f"igdb-{item['id']}",
        "title": item.get("name") or "Untitled",
        "cover": f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg",
        "year": year or 0,
        "genres": genres,
        "platforms": platform_ids,
        "developer": developer,
        "description": (item.get("summary") or "").strip()[:1000],
        "igdb_id": item["id"],
        "rating": round(item.get("total_rating") or 0, 1),
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_games(client_id: str, client_secret: str, total: int = 200) -> List[Dict[str, Any]]:
    """Fetch a mixed batch of popular + recent games from IGDB."""
    token = _get_token(client_id, client_secret)
    fields = (
        "fields name, summary, cover.image_id, genres.name, platforms.name, "
        "first_release_date, involved_companies.developer, involved_companies.company.name, "
        "total_rating, total_rating_count, hypes;"
    )
    base_filter = "where cover != null & version_parent = null"

    half = max(50, total // 2)

    popular_q = f"{fields} {base_filter} & total_rating != null & total_rating_count >= 200; sort total_rating desc; limit {half};"
    recent_cutoff = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp())
    recent_q = (
        f"{fields} {base_filter} & first_release_date > {recent_cutoff} "
        f"& total_rating_count >= 50; sort total_rating desc; limit {half};"
    )

    log.info("IGDB: fetching popular...")
    popular = _query(client_id, token, popular_q)
    time.sleep(0.3)
    log.info("IGDB: fetching recent...")
    recent = _query(client_id, token, recent_q)

    seen = set()
    out: List[Dict[str, Any]] = []
    for batch in (popular, recent):
        for item in batch:
            if item["id"] in seen:
                continue
            norm = _normalise(item)
            if norm:
                seen.add(item["id"])
                out.append(norm)
            if len(out) >= total:
                break
        if len(out) >= total:
            break

    log.info("IGDB: %d games normalised", len(out))
    return out


def import_to_db_sync(db_sync, total: int):
    """Synchronous helper for use from CLI; not used in async runtime."""
    cid = os.environ.get("TWITCH_CLIENT_ID")
    cs = os.environ.get("TWITCH_CLIENT_SECRET")
    if not cid or not cs:
        log.warning("TWITCH credentials missing — skipping IGDB import")
        return 0
    games = fetch_games(cid, cs, total)
    if not games:
        return 0
    db_sync.games.delete_many({})
    db_sync.games.insert_many(games)
    return len(games)
