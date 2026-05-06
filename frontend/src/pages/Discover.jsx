import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import GameCard from "@/components/GameCard";
import { useAuth } from "@/lib/auth-context";
import { Sparkles, Sword, Gem, TrendingUp, Compass } from "lucide-react";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";

function Section({ title, sub, icon: Ico, children, empty }) {
  return (
    <section className="space-y-4 mt-12 first:mt-0">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="gs-overline flex items-center gap-1.5"><Ico size={12} /> {sub}</div>
          <h2 className="font-heading font-black text-2xl sm:text-3xl uppercase tracking-tight mt-1">{title}</h2>
        </div>
      </div>
      {(!children || (Array.isArray(children) && children.length === 0)) ? (
        <div className="gs-card p-8 text-center font-mono text-sm text-muted-foreground">{empty}</div>
      ) : children}
    </section>
  );
}

export default function Discover() {
  const { user } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/discover").then((r) => setData(r.data)).catch(() => setData(null));
  }, []);

  if (!user) {
    return (
      <div className="text-center py-20 space-y-3">
        <Compass size={32} className="mx-auto text-primary" />
        <h1 className="font-heading font-black text-2xl uppercase tracking-tight">Inicia sessão</h1>
        <p className="text-sm text-muted-foreground">Para receber recomendações personalizadas precisas de uma conta.</p>
        <Link to="/login" className="inline-block mt-3 font-mono text-xs uppercase tracking-wider text-primary hover:underline">Entrar →</Link>
      </div>
    );
  }

  if (!data) {
    return <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>;
  }

  const { summary } = data;

  return (
    <div className="space-y-2">
      <header className="space-y-3 mb-8">
        <div className="gs-overline flex items-center gap-1.5"><Compass size={12} /> Para ti</div>
        <h1 className="font-heading font-black text-3xl sm:text-5xl uppercase tracking-tighter">Descobre</h1>
        <p className="text-sm text-muted-foreground max-w-xl">
          Recomendações com base nas tuas avaliações, jogo favorito e preferências de plataforma.
        </p>
        {(summary.top_genres?.length > 0 || summary.platforms?.length > 0) && (
          <div className="flex flex-wrap gap-2 pt-2">
            {summary.top_genres.map((g) => (
              <span key={g} className="font-mono text-[10px] uppercase tracking-wider px-2 py-1 border border-primary/40 bg-primary/5 text-primary rounded-sm">{g}</span>
            ))}
            {summary.platforms.map((p) => (
              <span key={p} className="font-mono text-[10px] uppercase tracking-wider px-2 py-1 border border-border rounded-sm">{p}</span>
            ))}
            <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-1 text-muted-foreground">{summary.review_count} jogos avaliados</span>
          </div>
        )}
      </header>

      <Section title="Para o teu gosto" sub="Baseado nas tuas avaliações" icon={Sparkles} empty="Avalia jogos para receber recomendações personalizadas">
        {data.by_taste.length === 0 ? null : (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {data.by_taste.slice(0, 12).map((g) => (<GameCard key={g.game_id} game={g} />))}
          </div>
        )}
      </Section>

      <Section title="Nas tuas plataformas" sub="Joga onde quiseres" icon={Sword} empty="Adiciona plataformas no teu perfil">
        {data.by_platform.length === 0 ? null : (
          <ScrollArea className="w-full">
            <div className="flex gap-4 pb-3">
              {data.by_platform.map((g) => (
                <div key={g.game_id} className="w-44 shrink-0"><GameCard game={g} /></div>
              ))}
            </div>
            <ScrollBar orientation="horizontal" />
          </ScrollArea>
        )}
      </Section>

      <Section title="Joias escondidas" sub="Subestimadas pela maioria" icon={Gem} empty="Sem sugestões para já">
        {data.hidden_gems.length === 0 ? null : (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {data.hidden_gems.slice(0, 12).map((g) => (<GameCard key={g.game_id} game={g} />))}
          </div>
        )}
      </Section>

      <Section title="Em alta" sub="Os mais avaliados pela comunidade" icon={TrendingUp} empty="Comunidade ainda calma">
        {data.trending.length === 0 ? null : (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {data.trending.slice(0, 12).map((g) => (<GameCard key={g.game_id} game={g} />))}
          </div>
        )}
      </Section>
    </div>
  );
}
