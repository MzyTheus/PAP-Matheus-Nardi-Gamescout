import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import GameCard from "@/components/GameCard";
import ReviewCard from "@/components/ReviewCard";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { ArrowRight, Flame, Sparkles, Skull, Zap } from "lucide-react";

const CATEGORIES = [
  { key: "Aventura", label: "Aventura", icon: Flame },
  { key: "RPG", label: "RPG", icon: Sparkles },
  { key: "FPS", label: "FPS", icon: Zap },
  { key: "Ação", label: "Ação", icon: Zap },
  { key: "Indie", label: "Indie", icon: Sparkles },
  { key: "Puzzle", label: "Puzzle", icon: Skull },
];

function Section({ title, sub, children, action }) {
  return (
    <section className="space-y-4 mt-12 first:mt-0">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="gs-overline">{sub}</div>
          <h2 className="font-heading font-black text-2xl sm:text-3xl uppercase tracking-tight mt-1">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export default function Home() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/games/featured").then((r) => setData(r.data)).catch(() => setData({ you_may_like: [], famous: [], horror: [], recent_titles: [], recent_reviews: [] }));
  }, []);

  if (!data) {
    return <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>;
  }

  return (
    <div className="space-y-2">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-sm border border-border gs-grid-bg">
        <img
          src="https://images.unsplash.com/photo-1698064534597-e039edaa0717?crop=entropy&cs=srgb&fm=jpg&w=1600&q=80"
          alt="" aria-hidden
          className="absolute inset-0 w-full h-full object-cover opacity-25"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-background via-background/80 to-transparent" />
        <div className="relative z-10 px-8 sm:px-12 py-16 sm:py-24 max-w-2xl">
          <div className="gs-overline animate-fade-up">Game.Scout v1.0</div>
          <h1 className="font-heading font-black text-4xl sm:text-5xl lg:text-6xl uppercase tracking-tighter leading-[0.95] mt-3 animate-fade-up" style={{ animationDelay: "120ms" }}>
            A bússola dos <span className="text-primary">verdadeiros jogadores</span>.
          </h1>
          <p className="text-base text-muted-foreground mt-4 max-w-md leading-relaxed animate-fade-up" style={{ animationDelay: "240ms" }}>
            Avaliações honestas, guias afiados, e quem te acompanha na próxima missão. Tudo num só sítio.
          </p>
          <div className="flex flex-wrap gap-3 mt-6 animate-fade-up" style={{ animationDelay: "360ms" }}>
            <Button asChild className="rounded-sm font-mono uppercase tracking-wider"><Link to="/jogos" data-testid="hero-explore">Explorar catálogo <ArrowRight size={14} className="ml-2" /></Link></Button>
            <Button asChild variant="outline" className="rounded-sm font-mono uppercase tracking-wider"><Link to="/ajuda" data-testid="hero-help">Pedidos de ajuda</Link></Button>
          </div>
        </div>
      </section>

      {/* Categories */}
      <Section title="Categorias" sub="Filtra pelo teu mood">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {CATEGORIES.map((c) => {
            const Ico = c.icon;
            return (
              <Link
                key={c.key}
                to={`/jogos?genre=${encodeURIComponent(c.key)}`}
                data-testid={`category-${c.key}`}
                className="gs-card p-4 flex items-center gap-3 group"
              >
                <span className="grid place-items-center w-10 h-10 border border-border rounded-sm group-hover:border-primary group-hover:text-primary transition-colors"><Ico size={18} /></span>
                <span className="font-mono uppercase text-sm tracking-wider">{c.label}</span>
              </Link>
            );
          })}
        </div>
      </Section>

      {/* You may like */}
      <Section title="Você pode gostar" sub="Curadoria GameScout" action={<Link to="/jogos" className="font-mono text-xs uppercase tracking-wider text-primary hover:underline">Ver tudo →</Link>}>
        <ScrollArea className="w-full">
          <div className="flex gap-4 pb-3">
            {data.you_may_like.map((g) => (
              <div key={g.game_id} className="w-44 shrink-0"><GameCard game={g} /></div>
            ))}
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      </Section>

      {/* Famous */}
      <Section title="Jogos famosos" sub="Os mais jogados">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {data.famous.map((g) => (<GameCard key={g.game_id} game={g} />))}
        </div>
      </Section>

      {/* Recent reviews */}
      <Section title="Avaliações recentes" sub="O que a comunidade diz" action={<Link to="/jogos" className="font-mono text-xs uppercase tracking-wider text-primary hover:underline">Mais →</Link>}>
        {data.recent_reviews.length === 0 ? (
          <div className="gs-card p-8 text-center text-muted-foreground text-sm">Ainda sem avaliações. Sê o primeiro!</div>
        ) : (
          <div className="grid md:grid-cols-2 gap-4">
            {data.recent_reviews.slice(0, 6).map((r) => (
              <ReviewCard key={r.review_id} review={r} showGame />
            ))}
          </div>
        )}
      </Section>

      {/* Horror section */}
      <Section title="Para o pessoal de Aventura" sub="Os mais imersivos">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {data.horror.map((g) => (<GameCard key={g.game_id} game={g} />))}
        </div>
      </Section>
    </div>
  );
}
