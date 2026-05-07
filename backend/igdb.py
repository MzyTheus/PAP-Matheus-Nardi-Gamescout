"""IGDB importer + Claude translator.

Auth: POST https://id.twitch.tv/oauth2/token (client_credentials)
Games: POST https://api.igdb.com/v4/games (text body, IGDB query language)
Cover: https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg
Translation: Claude Sonnet 4.5 via emergentintegrations (PT-PT).
"""
from __future__ import annotations
import os
import json
import logging
import time
import uuid
import asyncio
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

FIELDS = (
    "fields name, summary, cover.image_id, genres.name, platforms.name, "
    "first_release_date, involved_companies.developer, involved_companies.company.name, "
    "total_rating, total_rating_count, hypes;"
)


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
        timeout=25,
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

    year = None
    ts = item.get("first_release_date")
    if ts:
        try:
            year = datetime.fromtimestamp(int(ts), tz=timezone.utc).year
        except Exception:
            year = None

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
    developer = developer or "Desconhecido"

    return {
        "game_id": f"igdb-{item['id']}",
        "title": item.get("name") or "Untitled",
        "cover": f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg",
        "year": year or 0,
        "genres": genres,
        "platforms": platform_ids,
        "developer": developer,
        "description_en": (item.get("summary") or "").strip()[:1500],
        "description": (item.get("summary") or "").strip()[:1500],
        "igdb_id": item["id"],
        "rating": round(item.get("total_rating") or 0, 1),
        "rating_count": item.get("total_rating_count") or 0,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_games(client_id: str, client_secret: str, total: int = 500) -> List[Dict[str, Any]]:
    """Fetch a wide variety of games from IGDB (multiple buckets)."""
    token = _get_token(client_id, client_secret)
    base = "where cover != null & version_parent = null"
    recent_cutoff = int(datetime(2018, 1, 1, tzinfo=timezone.utc).timestamp())
    new_cutoff = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp())

    queries = [
        # All-time greats (very high quality)
        f"{FIELDS} {base} & total_rating != null & total_rating_count >= 300; sort total_rating desc; limit 200;",
        # Popular recent (last few years, well-rated)
        f"{FIELDS} {base} & first_release_date > {recent_cutoff} & total_rating_count >= 80; sort total_rating desc; limit 200;",
        # Most hyped recent
        f"{FIELDS} {base} & first_release_date > {new_cutoff} & hypes != null; sort hypes desc; limit 150;",
        # Indie gems
        f"{FIELDS} {base} & genres = (32) & total_rating_count >= 30; sort total_rating desc; limit 150;",
        # RPG focus
        f"{FIELDS} {base} & genres = (12) & total_rating_count >= 50; sort total_rating desc; limit 100;",
        # Adventure focus
        f"{FIELDS} {base} & genres = (31) & total_rating_count >= 50; sort total_rating desc; limit 100;",
        # FPS/Shooter
        f"{FIELDS} {base} & genres = (5) & total_rating_count >= 50; sort total_rating desc; limit 80;",
        # Strategy
        f"{FIELDS} {base} & genres = (15) & total_rating_count >= 30; sort total_rating desc; limit 60;",
        # Fighting
        f"{FIELDS} {base} & genres = (4) & total_rating_count >= 20; sort total_rating desc; limit 40;",
        # Sports/Racing
        f"{FIELDS} {base} & genres = (14,10) & total_rating_count >= 20; sort total_rating desc; limit 50;",
        # Survival/horror keyword themes (Survival Horror theme = 19)
        f"{FIELDS} {base} & themes = (19) & total_rating_count >= 5; sort total_rating desc; limit 100;",
        # Open world theme (38) — Minecraft, Terraria, No Man's Sky, etc
        f"{FIELDS} {base} & themes = (38) & total_rating_count >= 30; sort total_rating desc; limit 80;",
    ]

    # Specific franchise / popular game searches by name
    franchise_terms = [
        "Resident Evil", "Five Nights at Freddy", "Minecraft", "Terraria",
        "No Man's Sky", "Dead by Daylight", "Outlast", "Amnesia", "Silent Hill",
        "Dark Souls", "Bloodborne", "Sekiro", "Final Fantasy", "Halo",
        "Call of Duty", "Battlefield", "Fallout", "Skyrim", "Mass Effect",
        "Borderlands", "Assassin's Creed", "Far Cry", "Tomb Raider",
        "Mortal Kombat", "Street Fighter", "Tekken", "Devil May Cry",
        "Metal Gear", "Bioshock", "Portal", "Half-Life", "Doom",
        "Subnautica", "Stardew Valley", "Among Us", "Fall Guys",
        "Phasmophobia", "Lethal Company", "It Takes Two", "Hollow Knight",
        "Cuphead", "Undertale", "Celeste", "Hades", "Slay the Spire",
        "Dying Light", "Dishonored", "Prey", "Control", "Death Stranding",
        "Genshin Impact", "Honkai", "Apex Legends", "Overwatch", "Rainbow Six",
        "Rocket League", "Forza", "Gran Turismo", "F1", "NBA 2K",
        "Pokémon", "Kirby", "Mario", "Sonic", "Animal Crossing",
        "Splatoon", "Smash Bros", "Metroid", "Diablo", "Path of Exile",
    ]

    franchise_queries = [
        f"{FIELDS} {base} & name ~ *\"{name}\"*; limit 12;"
        for name in franchise_terms
    ]
    # Put franchise searches FIRST so they always make it into the import
    queries = franchise_queries + queries

    seen: set = set()
    out: List[Dict[str, Any]] = []
    for i, q in enumerate(queries):
        if len(out) >= total:
            break
        try:
            log.info("IGDB query %d/%d", i + 1, len(queries))
            batch = _query(client_id, token, q)
            for item in batch:
                if item["id"] in seen:
                    continue
                norm = _normalise(item)
                if norm:
                    seen.add(item["id"])
                    out.append(norm)
                    if len(out) >= total:
                        break
            time.sleep(0.3)
        except Exception as e:
            log.warning("IGDB query %d failed: %s", i + 1, e)
            continue

    log.info("IGDB: %d unique games normalised", len(out))
    return out[:total]


# ---------------------------------------------------------------------------
# Translation (Claude Sonnet 4.5 via emergentintegrations)
# ---------------------------------------------------------------------------

async def translate_descriptions_batch(games: List[Dict[str, Any]], batch_size: int = 8) -> int:
    """Translate `description_en` → `description` for each game (PT-PT). Returns count translated."""
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        log.warning("EMERGENT_LLM_KEY missing — keeping English descriptions")
        return 0

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        log.warning("emergentintegrations not available: %s", e)
        return 0

    todo = [g for g in games if (g.get("description_en") or "").strip()]
    if not todo:
        return 0

    translated = 0
    for i in range(0, len(todo), batch_size):
        chunk = todo[i:i + batch_size]
        items = [{"i": idx, "title": g["title"], "text": g["description_en"][:800]} for idx, g in enumerate(chunk)]
        prompt = (
            "Traduz para português europeu (pt-PT) cada descrição de videojogo. "
            "Mantém nomes próprios e títulos originais. Sê conciso e fiel. "
            "Devolve EXCLUSIVAMENTE JSON com lista de objetos [{\"i\": <int>, \"text\": <traducao>}], sem explicações.\n\n"
            f"INPUT:\n{json.dumps(items, ensure_ascii=False)}"
        )
        try:
            chat = LlmChat(
                api_key=key,
                session_id=f"gs-translate-{uuid.uuid4().hex[:8]}",
                system_message="És um tradutor profissional inglês→português europeu (pt-PT). Devolves apenas JSON válido.",
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            resp = await chat.send_message(UserMessage(text=prompt))
            text = (resp or "").strip()
            # extract JSON
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end == -1:
                raise ValueError("no JSON list in response")
            data = json.loads(text[start:end + 1])
            for entry in data:
                idx = entry.get("i")
                tr = (entry.get("text") or "").strip()
                if tr and isinstance(idx, int) and 0 <= idx < len(chunk):
                    chunk[idx]["description"] = tr
                    translated += 1
            log.info("Translated batch %d/%d (%d items)", (i // batch_size) + 1,
                     (len(todo) + batch_size - 1) // batch_size, len(chunk))
        except Exception as e:
            log.warning("Translation batch failed at %d: %s", i, e)
            await asyncio.sleep(0.5)
            continue

    return translated
