"""Social router — emojis, message reactions, review reactions, likes, comments.

This module uses a register() function pattern to avoid circular imports with
server.py. Dependencies are passed in explicitly when register() is called.
"""

from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
import uuid

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------
class ReactionIn(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)


class CommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=600)


class CustomEmojiIn(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)
    name: Optional[str] = Field(default=None, max_length=40)


# ---------------------------------------------------------------------------
# Aggregation helpers (pure functions over deps['db'])
# ---------------------------------------------------------------------------
async def _reactions_for_msgs(db, msg_ids: list, viewer_id: Optional[str] = None) -> dict:
    if not msg_ids:
        return {}
    pipe = [
        {"$match": {"msg_id": {"$in": msg_ids}}},
        {"$group": {"_id": {"msg_id": "$msg_id", "emoji": "$emoji"}, "count": {"$sum": 1}, "users": {"$push": "$user_id"}}},
    ]
    out: dict = {}
    async for d in db.message_reactions.aggregate(pipe):
        mid = d["_id"]["msg_id"]
        out.setdefault(mid, []).append({
            "emoji": d["_id"]["emoji"],
            "count": d["count"],
            "mine": bool(viewer_id and viewer_id in d.get("users", [])),
        })
    for mid in out:
        out[mid].sort(key=lambda r: -r["count"])
    return out


async def _review_reactions_for(db, review_ids: list, viewer_id: Optional[str] = None) -> dict:
    if not review_ids:
        return {}
    pipe = [
        {"$match": {"review_id": {"$in": review_ids}}},
        {"$group": {"_id": {"review_id": "$review_id", "emoji": "$emoji"}, "count": {"$sum": 1}, "users": {"$push": "$user_id"}}},
    ]
    out: dict = {}
    async for d in db.review_reactions.aggregate(pipe):
        rid = d["_id"]["review_id"]
        out.setdefault(rid, []).append({
            "emoji": d["_id"]["emoji"],
            "count": d["count"],
            "mine": bool(viewer_id and viewer_id in d.get("users", [])),
        })
    for rid in out:
        out[rid].sort(key=lambda r: -r["count"])
    return out


async def _likes_summary(db, review_ids: list, viewer_id: Optional[str] = None) -> dict:
    if not review_ids:
        return {}
    out = {}
    cur = db.review_likes.aggregate([
        {"$match": {"review_id": {"$in": review_ids}}},
        {"$group": {"_id": "$review_id", "count": {"$sum": 1}, "users": {"$push": "$user_id"}}},
    ])
    async for d in cur:
        out[d["_id"]] = {"count": d["count"], "mine": bool(viewer_id and viewer_id in d.get("users", []))}
    return out


# ---------------------------------------------------------------------------
# Register routes onto an existing APIRouter
# ---------------------------------------------------------------------------
def register(*, api, db, get_current_user, get_verified_user, get_current_user_optional,
             require_admin, assert_valid_emoji, reload_custom_emojis, default_emojis):
    """Attach all social endpoints to the provided `api` router."""

    @api.get("/emojis")
    async def list_emojis():
        cur = db.custom_emojis.find({}, {"_id": 0}).sort("created_at", 1)
        custom = [c async for c in cur]
        return {"basic": default_emojis, "custom": custom}

    @api.post("/admin/emojis")
    async def admin_add_emoji(payload: CustomEmojiIn, admin: dict = Depends(require_admin)):
        e = payload.emoji.strip()
        if not e:
            raise HTTPException(400, "Emoji vazio")
        doc = {
            "emoji_id": f"em_{uuid.uuid4().hex[:8]}",
            "emoji": e,
            "name": (payload.name or e).strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": admin["user_id"],
        }
        try:
            await db.custom_emojis.insert_one(doc)
        except Exception:
            raise HTTPException(400, "Emoji já adicionado")
        await reload_custom_emojis()
        doc.pop("_id", None)
        return doc

    @api.delete("/admin/emojis/{emoji_id}")
    async def admin_remove_emoji(emoji_id: str, _: dict = Depends(require_admin)):
        res = await db.custom_emojis.delete_one({"emoji_id": emoji_id})
        if res.deleted_count == 0:
            raise HTTPException(404, "Emoji não encontrado")
        await reload_custom_emojis()
        return {"ok": True}

    # ----- Message reactions (DM + community) -----
    @api.post("/messages/{msg_id}/reactions")
    async def toggle_msg_reaction(msg_id: str, payload: ReactionIn, user: dict = Depends(get_verified_user)):
        assert_valid_emoji(payload.emoji)
        msg = await db.messages.find_one({"msg_id": msg_id}, {"_id": 0})
        if not msg:
            raise HTTPException(404, "Mensagem não encontrada")
        me = user["user_id"]
        if msg.get("type") == "dm":
            parts = msg.get("thread_key", "").replace("dm::", "").split("::")
            if me not in parts:
                raise HTTPException(403, "Sem acesso à conversa")
        elif msg.get("type") == "community":
            c = await db.communities.find_one({"community_id": msg.get("community_id")}, {"_id": 0, "members": 1})
            if not c or me not in (c.get("members") or []):
                raise HTTPException(403, "Junta-te à comunidade primeiro")
        existing = await db.message_reactions.find_one({"msg_id": msg_id, "user_id": me, "emoji": payload.emoji})
        if existing:
            await db.message_reactions.delete_one({"_id": existing["_id"]})
            action = "removed"
        else:
            await db.message_reactions.insert_one({
                "msg_id": msg_id,
                "user_id": me,
                "emoji": payload.emoji,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            action = "added"
        reactions = (await _reactions_for_msgs(db, [msg_id], me)).get(msg_id, [])
        return {"action": action, "reactions": reactions}

    @api.get("/messages/{msg_id}/reactions")
    async def get_msg_reactions(msg_id: str, user: dict = Depends(get_current_user)):
        return (await _reactions_for_msgs(db, [msg_id], user["user_id"])).get(msg_id, [])

    # ----- Review reactions / likes / comments -----
    @api.post("/reviews/{review_id}/reactions")
    async def toggle_review_reaction(review_id: str, payload: ReactionIn, user: dict = Depends(get_verified_user)):
        assert_valid_emoji(payload.emoji)
        r = await db.reviews.find_one({"review_id": review_id}, {"_id": 0, "review_id": 1})
        if not r:
            raise HTTPException(404, "Avaliação não encontrada")
        me = user["user_id"]
        existing = await db.review_reactions.find_one({"review_id": review_id, "user_id": me, "emoji": payload.emoji})
        if existing:
            await db.review_reactions.delete_one({"_id": existing["_id"]})
            action = "removed"
        else:
            await db.review_reactions.insert_one({
                "review_id": review_id,
                "user_id": me,
                "emoji": payload.emoji,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            action = "added"
        reactions = (await _review_reactions_for(db, [review_id], me)).get(review_id, [])
        return {"action": action, "reactions": reactions}

    @api.get("/reviews/{review_id}/reactions")
    async def get_review_reactions(review_id: str, request: Request):
        viewer = await get_current_user_optional(request)
        vid = viewer["user_id"] if viewer else None
        return (await _review_reactions_for(db, [review_id], vid)).get(review_id, [])

    @api.post("/reviews/{review_id}/like")
    async def toggle_review_like(review_id: str, user: dict = Depends(get_verified_user)):
        r = await db.reviews.find_one({"review_id": review_id}, {"_id": 0, "review_id": 1})
        if not r:
            raise HTTPException(404, "Avaliação não encontrada")
        me = user["user_id"]
        existing = await db.review_likes.find_one({"review_id": review_id, "user_id": me})
        if existing:
            await db.review_likes.delete_one({"_id": existing["_id"]})
            action = "removed"
        else:
            await db.review_likes.insert_one({
                "review_id": review_id,
                "user_id": me,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            action = "added"
        summary = (await _likes_summary(db, [review_id], me)).get(review_id, {"count": 0, "mine": False})
        return {"action": action, **summary}

    @api.get("/reviews/{review_id}/comments")
    async def list_review_comments(review_id: str):
        cur = db.review_comments.find({"review_id": review_id}, {"_id": 0}).sort("created_at", 1)
        return [c async for c in cur]

    @api.post("/reviews/{review_id}/comments")
    async def post_review_comment(review_id: str, payload: CommentIn, user: dict = Depends(get_verified_user)):
        r = await db.reviews.find_one({"review_id": review_id}, {"_id": 0, "review_id": 1})
        if not r:
            raise HTTPException(404, "Avaliação não encontrada")
        doc = {
            "comment_id": f"cm_{uuid.uuid4().hex[:12]}",
            "review_id": review_id,
            "user_id": user["user_id"],
            "user_name": user.get("name"),
            "user_picture": user.get("picture"),
            "content": payload.content.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.review_comments.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @api.delete("/reviews/comments/{comment_id}")
    async def delete_review_comment(comment_id: str, user: dict = Depends(get_current_user)):
        c = await db.review_comments.find_one({"comment_id": comment_id})
        if not c:
            raise HTTPException(404, "Comentário não encontrado")
        if c["user_id"] != user["user_id"] and user.get("role") != "admin":
            raise HTTPException(403, "Sem permissão")
        await db.review_comments.delete_one({"comment_id": comment_id})
        return {"ok": True}

    # Return aggregation helpers so server.py can reuse them (e.g. attach reactions to messages list)
    return {
        "reactions_for_msgs": lambda msg_ids, viewer_id=None: _reactions_for_msgs(db, msg_ids, viewer_id),
        "review_reactions_for": lambda rids, vid=None: _review_reactions_for(db, rids, vid),
        "likes_summary": lambda rids, vid=None: _likes_summary(db, rids, vid),
    }
