import { Link } from "react-router-dom";
import { Star, Heart } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth-context";
import { api } from "../lib/api";
import { toast } from "sonner";

export default function GameCard({ game, compact = false, showWishlist = true }) {
  const { user, refresh } = useAuth();
  const [inWishlist, setInWishlist] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setInWishlist(!!user?.wishlist?.includes(game.game_id));
  }, [user, game.game_id]);

  const toggleWishlist = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!user) { toast.error("Inicia sessão para usar a wishlist"); return; }
    setBusy(true);
    try {
      if (inWishlist) {
        await api.delete(`/wishlist/${game.game_id}`);
        toast.success("Removido da wishlist");
      } else {
        await api.post(`/wishlist/${game.game_id}`);
        toast.success("Adicionado à wishlist");
      }
      setInWishlist(!inWishlist);
      refresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Link
      to={`/jogos/${game.game_id}`}
      data-testid={`game-card-${game.game_id}`}
      className="group block gs-card overflow-hidden relative"
    >
      <div className="aspect-[3/4] relative overflow-hidden bg-muted">
        <img
          src={game.cover}
          alt={game.title}
          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-background/95 via-background/30 to-transparent opacity-90" />
        {game.year ? (
          <span className="absolute top-2 right-2 font-mono text-[10px] px-2 py-1 bg-background/80 border border-border rounded-sm tracking-wider">
            {game.year}
          </span>
        ) : null}
        {showWishlist && user && (
          <button
            type="button"
            disabled={busy}
            onClick={toggleWishlist}
            data-testid={`wishlist-toggle-${game.game_id}`}
            className={`absolute top-2 left-2 grid place-items-center w-8 h-8 rounded-sm border transition-all ${
              inWishlist
                ? "bg-primary border-primary text-primary-foreground"
                : "bg-background/80 border-border hover:border-primary hover:text-primary"
            }`}
            title={inWishlist ? "Remover da wishlist" : "Adicionar à wishlist"}
            aria-label={inWishlist ? "Remover da wishlist" : "Adicionar à wishlist"}
          >
            <Heart size={14} className={inWishlist ? "fill-current" : ""} />
          </button>
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
