import { Link, useNavigate } from "react-router-dom";
import { Star, ThumbsUp, ThumbsDown, Clock, MoreVertical, Edit2, Trash2, Heart, MessageCircle, Send } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { PLATFORM_LABEL } from "../lib/game-data";
import { cacheBust } from "../lib/format";
import { useAuth } from "../lib/auth-context";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "./ui/alert-dialog";
import { api } from "../lib/api";
import { toast } from "sonner";
import { useEffect, useState } from "react";
import ReactionPicker from "./ReactionPicker";
import { Input } from "./ui/input";
import { Button } from "./ui/button";

export default function ReviewCard({ review, showGame = false, onChanged }) {
  const { user } = useAuth();
  const nav = useNavigate();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [reactions, setReactions] = useState([]);
  const [likes, setLikes] = useState({ count: 0, mine: false });
  const [comments, setComments] = useState([]);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const isOwner = user && (user.user_id === review.user_id || user.role === "admin");

  // Load reactions + likes count on mount (cheap aggregates)
  useEffect(() => {
    api.get(`/reviews/${review.review_id}/reactions`).then((r) => setReactions(r.data || [])).catch(() => null);
    api.get(`/reviews/${review.review_id}/comments`).then((r) => setComments(r.data || [])).catch(() => null);
    // likes: we don't have GET so derive from local optimistic state OR call POST? simpler: store via reviews.like_count if present
    if (typeof review.like_count === "number") setLikes({ count: review.like_count, mine: !!review.liked_by_me });
  }, [review.review_id]);

  const onDelete = async () => {
    try {
      await api.delete(`/reviews/${review.review_id}`);
      toast.success("Avaliação removida");
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  const toggleReaction = async (emoji) => {
    try {
      const { data } = await api.post(`/reviews/${review.review_id}/reactions`, { emoji });
      setReactions(data.reactions || []);
    } catch (e) { toast.error(e.response?.data?.detail || "Faz login para reagir"); }
  };

  const toggleLike = async () => {
    try {
      const { data } = await api.post(`/reviews/${review.review_id}/like`);
      setLikes({ count: data.count, mine: data.action === "liked" });
    } catch (e) { toast.error(e.response?.data?.detail || "Faz login para curtir"); }
  };

  const postComment = async (e) => {
    e.preventDefault();
    const txt = draft.trim();
    if (!txt) return;
    try {
      const { data } = await api.post(`/reviews/${review.review_id}/comments`, { content: txt });
      setComments((p) => [...p, data]);
      setDraft("");
    } catch (err) { toast.error(err.response?.data?.detail || "Erro"); }
  };

  const deleteComment = async (cid) => {
    try {
      await api.delete(`/reviews/comments/${cid}`);
      setComments((p) => p.filter((c) => c.comment_id !== cid));
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  return (
    <article data-testid={`review-card-${review.review_id}`} className="gs-card p-5 space-y-3 group/review">
      <div className="flex items-start justify-between gap-3">
        <Link to={`/perfil/${review.user_id}`} className="flex items-center gap-3 group/u">
          <Avatar className="h-9 w-9 rounded-sm">
            <AvatarImage src={review.user_picture ? cacheBust(review.user_picture, (review.user_picture || "").length) : null} />
            <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-xs">{(review.user_name || "U").slice(0, 2).toUpperCase()}</AvatarFallback>
          </Avatar>
          <div>
            <div className="font-semibold text-sm group-hover/u:text-primary transition-colors">{review.user_name}</div>
            <div className="font-mono text-[10px] text-muted-foreground tracking-wider uppercase">
              {review.is_complete ? "Avaliação Completa · +50pts" : "Avaliação Parcial · +25pts"}
            </div>
          </div>
        </Link>
        <div className="flex items-center gap-2">
          <div className="flex flex-col items-center px-2 py-1 border border-primary/40 bg-primary/10 rounded-sm">
            <div className="flex items-center gap-1">
              <Star size={14} className="fill-primary text-primary" />
              <span className="font-mono font-bold">{(review.score ?? review.rating).toFixed ? (review.score ?? review.rating).toFixed(1) : (review.score ?? review.rating)}/10</span>
            </div>
            {review.score != null && review.score !== review.rating && (
              <span className="font-mono text-[9px] text-muted-foreground tracking-wider mt-0.5">geral {review.rating}</span>
            )}
          </div>
          {isOwner && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid={`review-menu-${review.review_id}`} className="p-1 rounded-sm hover:bg-muted text-muted-foreground"><MoreVertical size={16}/></button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="rounded-sm">
                <DropdownMenuItem data-testid={`review-edit-${review.review_id}`} onClick={() => nav(`/jogos/${review.game_id}/avaliar?edit=1`)}>
                  <Edit2 size={14} className="mr-2"/> Editar
                </DropdownMenuItem>
                <DropdownMenuItem data-testid={`review-delete-${review.review_id}`} className="text-destructive focus:text-destructive" onClick={() => setConfirmOpen(true)}>
                  <Trash2 size={14} className="mr-2"/> Apagar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>

      {showGame && review.game_title && (
        <Link to={`/jogos/${review.game_id}`} className="flex items-center gap-2 text-xs hover:text-primary">
          <img src={review.game_cover} alt="" className="w-8 h-10 object-cover rounded-sm" />
          <span className="font-medium">{review.game_title}</span>
        </Link>
      )}

      {review.note && (
        <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-line">{review.note}</p>
      )}

      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-border">
        {review.hours_played != null && (
          <span className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
            <Clock size={12} /> {review.hours_played}h
          </span>
        )}
        {review.platform && (
          <span className="font-mono text-[10px] tracking-wider uppercase px-2 py-0.5 border border-border rounded-sm">
            {PLATFORM_LABEL[review.platform] || review.platform}
          </span>
        )}
        {review.recommends === true && (
          <span className="inline-flex items-center gap-1 font-mono text-xs text-green-500"><ThumbsUp size={12} /> Recomenda</span>
        )}
        {review.recommends === false && (
          <span className="inline-flex items-center gap-1 font-mono text-xs text-red-400"><ThumbsDown size={12} /> Não recomenda</span>
        )}
        {review.is_complete && (
          <div className="ml-auto hidden md:flex flex-wrap gap-x-2.5 gap-y-1 font-mono text-[10px] text-muted-foreground justify-end">
            <span>GRA <b className="text-foreground">{review.graphics}</b></span>
            <span>HIS <b className="text-foreground">{review.story}</b></span>
            <span>JOG <b className="text-foreground">{review.gameplay}</b></span>
            <span>TUT <b className="text-foreground">{review.tutorial}</b></span>
            {review.audio != null && <span>AUD <b className="text-foreground">{review.audio}</b></span>}
            {review.performance != null && <span>PER <b className="text-foreground">{review.performance}</b></span>}
            {review.fun != null && <span>DIV <b className="text-foreground">{review.fun}</b></span>}
          </div>
        )}
      </div>

      {/* Reactions + actions row */}
      <div className="flex flex-wrap items-center gap-1 pt-2 border-t border-border">
        {reactions.map((r) => (
          <button
            key={r.emoji}
            data-testid={`review-reaction-${review.review_id}-${r.emoji}`}
            onClick={() => toggleReaction(r.emoji)}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border text-xs transition ${r.mine ? "bg-primary/10 border-primary text-primary" : "border-border hover:border-primary"}`}
          >
            <span>{r.emoji}</span>
            <span className="font-mono text-[10px]">{r.count}</span>
          </button>
        ))}
        <ReactionPicker testIdPrefix={`review-react-${review.review_id}`} onPick={toggleReaction} />
        <div className="ml-auto flex items-center gap-2">
          <button
            data-testid={`review-like-${review.review_id}`}
            onClick={toggleLike}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border text-xs transition ${likes.mine ? "bg-red-500/10 border-red-500 text-red-400" : "border-border hover:border-red-500/60"}`}
          >
            <Heart size={12} className={likes.mine ? "fill-current" : ""} />
            <span className="font-mono text-[10px]">{likes.count}</span>
          </button>
          <button
            data-testid={`review-comments-toggle-${review.review_id}`}
            onClick={() => setCommentsOpen((v) => !v)}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-border hover:border-primary text-xs transition"
          >
            <MessageCircle size={12} />
            <span className="font-mono text-[10px]">{comments.length}</span>
          </button>
        </div>
      </div>

      {commentsOpen && (
        <div className="pt-2 border-t border-border space-y-2" data-testid={`review-comments-${review.review_id}`}>
          {comments.length === 0 ? (
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground text-center py-2">Sem comentários — sê o primeiro!</div>
          ) : comments.map((c) => {
            const own = user && (user.user_id === c.user_id || user.role === "admin");
            return (
              <div key={c.comment_id} data-testid={`review-comment-${c.comment_id}`} className="flex items-start gap-2 text-sm group/com">
                <Link to={`/perfil/${c.user_id}`}>
                  <Avatar className="h-6 w-6 rounded-sm">
                    <AvatarImage src={c.user_picture ? cacheBust(c.user_picture, (c.user_picture || "").length) : null} />
                    <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-[9px]">{(c.user_name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                  </Avatar>
                </Link>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <Link to={`/perfil/${c.user_id}`} className="font-semibold text-xs hover:text-primary">{c.user_name}</Link>
                    <span className="font-mono text-[9px] text-muted-foreground">{new Date(c.created_at).toLocaleString("pt-PT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <div className="text-sm whitespace-pre-line break-words">{c.content}</div>
                </div>
                {own && (
                  <button data-testid={`review-comment-delete-${c.comment_id}`} onClick={() => deleteComment(c.comment_id)} className="opacity-0 group-hover/com:opacity-100 transition text-muted-foreground hover:text-destructive p-1"><Trash2 size={12}/></button>
                )}
              </div>
            );
          })}
          {user && (
            <form onSubmit={postComment} className="flex gap-2 pt-1">
              <Input data-testid={`review-comment-input-${review.review_id}`} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Comentar..." maxLength={600} className="rounded-sm h-8 text-sm" />
              <Button type="submit" size="sm" disabled={!draft.trim()} data-testid={`review-comment-send-${review.review_id}`} className="rounded-sm h-8 px-2"><Send size={14}/></Button>
            </form>
          )}
        </div>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent className="rounded-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Apagar avaliação?</AlertDialogTitle>
            <AlertDialogDescription>Esta ação não pode ser revertida.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-sm">Cancelar</AlertDialogCancel>
            <AlertDialogAction data-testid={`review-delete-confirm-${review.review_id}`} className="rounded-sm" onClick={onDelete}>Apagar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </article>
  );
}
