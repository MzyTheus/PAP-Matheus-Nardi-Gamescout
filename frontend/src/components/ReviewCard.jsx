import { Link } from "react-router-dom";
import { Star, ThumbsUp, ThumbsDown, Clock } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { PLATFORM_LABEL } from "../lib/game-data";

export default function ReviewCard({ review, showGame = false }) {
  return (
    <article data-testid={`review-card-${review.review_id}`} className="gs-card p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <Link to={`/perfil/${review.user_id}`} className="flex items-center gap-3 group/u">
          <Avatar className="h-9 w-9 rounded-sm">
            <AvatarImage src={review.user_picture} />
            <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-xs">{(review.user_name || "U").slice(0, 2).toUpperCase()}</AvatarFallback>
          </Avatar>
          <div>
            <div className="font-semibold text-sm group-hover/u:text-primary transition-colors">{review.user_name}</div>
            <div className="font-mono text-[10px] text-muted-foreground tracking-wider uppercase">
              {review.is_complete ? "Avaliação Completa · +50pts" : "Avaliação Parcial · +25pts"}
            </div>
          </div>
        </Link>
        <div className="flex items-center gap-1 px-2 py-1 border border-primary/40 bg-primary/10 rounded-sm">
          <Star size={14} className="fill-primary text-primary" />
          <span className="font-mono font-bold">{review.rating}/10</span>
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
          <div className="ml-auto hidden sm:flex gap-3 font-mono text-[10px] text-muted-foreground">
            <span>GRA <b className="text-foreground">{review.graphics}</b></span>
            <span>HIS <b className="text-foreground">{review.story}</b></span>
            <span>JOG <b className="text-foreground">{review.gameplay}</b></span>
            <span>TUT <b className="text-foreground">{review.tutorial}</b></span>
          </div>
        )}
      </div>
    </article>
  );
}
