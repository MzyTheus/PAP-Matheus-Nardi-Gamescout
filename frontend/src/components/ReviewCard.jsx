import { Link, useNavigate } from "react-router-dom";
import { Star, ThumbsUp, ThumbsDown, Clock, MoreVertical, Edit2, Trash2 } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { PLATFORM_LABEL } from "../lib/game-data";
import { cacheBust } from "../lib/format";
import { useAuth } from "../lib/auth-context";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "./ui/alert-dialog";
import { api } from "../lib/api";
import { toast } from "sonner";
import { useState } from "react";

export default function ReviewCard({ review, showGame = false, onChanged }) {
  const { user } = useAuth();
  const nav = useNavigate();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const isOwner = user && (user.user_id === review.user_id || user.role === "admin");

  const onDelete = async () => {
    try {
      await api.delete(`/reviews/${review.review_id}`);
      toast.success("Avaliação removida");
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  return (
    <article data-testid={`review-card-${review.review_id}`} className="gs-card p-5 space-y-3">
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
