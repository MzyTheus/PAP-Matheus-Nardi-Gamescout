import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import ReviewCard from "@/components/ReviewCard";
import { useAuth } from "@/lib/auth-context";
import { Star, Calendar, Cpu, BookOpen, MessageCircleQuestion, ArrowLeft } from "lucide-react";
import { PLATFORM_LABEL } from "@/lib/game-data";

const CATEGORY_LABEL = {
  "dica": "Dica",
  "tutorial": "Tutorial",
  "como-zerar": "Como zerar",
  "estrategia": "Estratégia",
  "macete": "Macete",
};

export default function GameDetail() {
  const { gameId } = useParams();
  const { user } = useAuth();
  const [game, setGame] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [guides, setGuides] = useState([]);

  useEffect(() => {
    api.get(`/games/${gameId}`).then((r) => setGame(r.data));
    api.get(`/games/${gameId}/reviews`).then((r) => setReviews(r.data));
    api.get(`/games/${gameId}/guides`).then((r) => setGuides(r.data));
  }, [gameId]);

  if (!game) return <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>;

  const canCreateGuide = user && (user.points >= 50);

  return (
    <div className="space-y-8">
      <Link to="/jogos" className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:text-primary transition-colors">
        <ArrowLeft size={14} /> Voltar ao catálogo
      </Link>

      <div className="grid md:grid-cols-[260px_1fr] gap-8">
        <div className="aspect-[3/4] gs-card overflow-hidden">
          <img src={game.cover} alt={game.title} className="w-full h-full object-cover" />
        </div>
        <div className="space-y-5">
          <div>
            <div className="gs-overline mb-2">{game.developer} · {game.year}</div>
            <h1 className="font-heading font-black text-3xl sm:text-5xl uppercase tracking-tighter leading-tight">{game.title}</h1>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {game.avg_rating != null && (
              <div className="flex items-center gap-2 px-3 py-2 border border-primary/40 bg-primary/10 rounded-sm">
                <Star size={16} className="fill-primary text-primary" />
                <span className="font-mono font-bold text-lg">{game.avg_rating}/10</span>
                <span className="font-mono text-xs text-muted-foreground">({game.review_count} avaliações)</span>
              </div>
            )}
            {game.review_count === 0 && (
              <div className="font-mono text-xs text-muted-foreground tracking-wider uppercase">Ainda sem avaliações</div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {game.genres?.map((g) => (
              <span key={g} className="font-mono text-[11px] uppercase tracking-wider px-2.5 py-1 border border-border rounded-sm">{g}</span>
            ))}
          </div>

          <p className="text-base leading-relaxed text-foreground/90 max-w-2xl">{game.description}</p>

          <div className="flex flex-wrap gap-2">
            <div className="font-mono text-xs uppercase tracking-widest text-muted-foreground mr-2 self-center">Plataformas:</div>
            {game.platforms?.map((p) => (
              <span key={p} className="font-mono text-[11px] uppercase tracking-wider px-2.5 py-1 border border-primary/40 bg-primary/5 text-primary rounded-sm">
                {PLATFORM_LABEL[p] || p}
              </span>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            <Button asChild data-testid="game-review-btn" className="rounded-sm font-mono uppercase tracking-wider"><Link to={`/jogos/${gameId}/avaliar`}>Avaliar este jogo</Link></Button>
            {canCreateGuide && (
              <Button asChild variant="outline" data-testid="game-guide-btn" className="rounded-sm font-mono uppercase tracking-wider"><Link to={`/jogos/${gameId}/guia/novo`}>Criar guia</Link></Button>
            )}
          </div>
        </div>
      </div>

      <Tabs defaultValue="reviews" className="space-y-6">
        <TabsList className="bg-transparent p-0 border-b border-border rounded-none h-auto gap-6 justify-start">
          <TabsTrigger
            value="reviews"
            data-testid="tab-reviews"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none px-0 py-3 font-mono uppercase tracking-wider text-sm"
          >
            <Star size={14} className="mr-2" /> Avaliações ({reviews.length})
          </TabsTrigger>
          <TabsTrigger
            value="guides"
            data-testid="tab-guides"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none px-0 py-3 font-mono uppercase tracking-wider text-sm"
          >
            <BookOpen size={14} className="mr-2" /> Guias ({guides.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="reviews" className="space-y-4">
          {reviews.length === 0 ? (
            <div className="gs-card p-12 text-center">
              <MessageCircleQuestion size={32} className="mx-auto text-primary mb-3" />
              <div className="font-heading uppercase text-lg tracking-tight">Sê o primeiro a avaliar</div>
              <div className="font-mono text-sm text-muted-foreground mt-2">Partilha a tua opinião e ganha pontos.</div>
            </div>
          ) : (
            reviews.map((r) => <ReviewCard key={r.review_id} review={r} />)
          )}
        </TabsContent>

        <TabsContent value="guides" className="space-y-4">
          {guides.length === 0 ? (
            <div className="gs-card p-12 text-center">
              <BookOpen size={32} className="mx-auto text-primary mb-3" />
              <div className="font-heading uppercase text-lg tracking-tight">Ainda sem guias</div>
              <div className="font-mono text-sm text-muted-foreground mt-2">
                {canCreateGuide ? "Cria o primeiro guia da comunidade!" : "Atinge o nível Explorador (50 pts) para criar guias."}
              </div>
            </div>
          ) : (
            guides.map((g) => (
              <article key={g.guide_id} data-testid={`guide-${g.guide_id}`} className="gs-card p-5 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-primary">{CATEGORY_LABEL[g.category] || g.category}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">por {g.author_name}</span>
                  </div>
                </div>
                <h3 className="font-heading text-xl font-bold tracking-tight">{g.title}</h3>
                <p className="text-sm leading-relaxed whitespace-pre-line text-foreground/90">{g.content}</p>
              </article>
            ))
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
