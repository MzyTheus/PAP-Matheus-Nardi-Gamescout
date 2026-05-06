import { Link } from "react-router-dom";
import { Star } from "lucide-react";

export default function GameCard({ game, compact = false }) {
  return (
    <Link
      to={`/jogos/${game.game_id}`}
      data-testid={`game-card-${game.game_id}`}
      className="group block gs-card overflow-hidden"
    >
      <div className="aspect-[3/4] relative overflow-hidden bg-muted">
        <img
          src={game.cover}
          alt={game.title}
          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-background/95 via-background/30 to-transparent opacity-90" />
        {game.year && (
          <span className="absolute top-2 right-2 font-mono text-[10px] px-2 py-1 bg-background/80 border border-border rounded-sm tracking-wider">
            {game.year}
          </span>
        )}
        <div className="absolute bottom-0 left-0 right-0 p-3">
          <h3 className="font-heading font-bold text-sm leading-tight line-clamp-2 mb-1">{game.title}</h3>
          {!compact && game.genres?.[0] && (
            <span className="font-mono text-[10px] text-primary tracking-wider uppercase">{game.genres[0]}</span>
          )}
        </div>
      </div>
      {!compact && game.avg_rating !== undefined && game.avg_rating !== null && (
        <div className="px-3 py-2 flex items-center justify-between border-t border-border">
          <div className="flex items-center gap-1">
            <Star size={12} className="fill-primary text-primary" />
            <span className="font-mono font-bold text-sm">{game.avg_rating}</span>
          </div>
          <span className="font-mono text-[10px] text-muted-foreground">{game.review_count || 0} avaliações</span>
        </div>
      )}
    </Link>
  );
}
