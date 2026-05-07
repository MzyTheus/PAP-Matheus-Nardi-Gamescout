import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Trophy, Medal, Award, Star } from "lucide-react";
import { GENRES, PLATFORMS, PLATFORM_LABEL } from "@/lib/game-data";

export default function TopGames() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [genre, setGenre] = useState("");
  const [platform, setPlatform] = useState("");

  useEffect(() => {
    setLoading(true);
    const sp = { limit: 100 };
    if (genre) sp.genre = genre;
    if (platform) sp.platform = platform;
    api.get("/games/top", { params: sp })
      .then((r) => setList(r.data))
      .finally(() => setLoading(false));
  }, [genre, platform]);

  return (
    <div className="space-y-8">
      <header>
        <div className="gs-overline flex items-center gap-1.5"><Trophy size={12}/> Hall da Fama</div>
        <h1 className="font-heading font-black text-3xl sm:text-5xl uppercase tracking-tighter mt-1">Top Jogos</h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-xl">
          Ranking ponderado: combina nota média e número de avaliações (Bayesian average) para evitar resultados injustos.
          Um jogo com 9.9 e 1000 reviews vence um com 10.0 e 1 review.
        </p>
      </header>

      <div className="space-y-3">
        <div>
          <div className="font-mono text-xs uppercase tracking-widest text-muted-foreground mb-2">Género</div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setGenre("")} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${!genre ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>Todos</button>
            {GENRES.slice(0, 12).map((g) => (
              <button key={g} onClick={() => setGenre(genre === g ? "" : g)} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${genre === g ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>{g}</button>
            ))}
          </div>
        </div>
        <div>
          <div className="font-mono text-xs uppercase tracking-widest text-muted-foreground mb-2">Plataforma</div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setPlatform("")} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${!platform ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>Todas</button>
            {PLATFORMS.map((p) => (
              <button key={p.id} onClick={() => setPlatform(platform === p.id ? "" : p.id)} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${platform === p.id ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>{p.label}</button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>
      ) : list.length === 0 ? (
        <div className="gs-card p-12 text-center">
          <div className="font-heading text-xl uppercase tracking-tight">Sem jogos para este filtro</div>
        </div>
      ) : (
        <ol className="space-y-2">
          {list.map((g, i) => {
            const rank = i + 1;
            const medal = rank === 1 ? "text-yellow-400" : rank === 2 ? "text-gray-300" : rank === 3 ? "text-amber-700" : "text-muted-foreground";
            return (
              <li key={g.game_id}>
                <Link to={`/jogos/${g.game_id}`} data-testid={`top-game-${g.game_id}`} className="gs-card p-4 flex items-center gap-4 group">
                  <div className={`w-10 text-center font-heading font-black text-xl ${medal}`}>
                    {rank <= 3 ? <Medal size={28} className="mx-auto"/> : `#${rank}`}
                  </div>
                  <img src={g.cover} alt="" className="w-12 h-16 object-cover rounded-sm" />
                  <div className="flex-1 min-w-0">
                    <div className="font-heading font-bold text-base sm:text-lg group-hover:text-primary transition-colors truncate">{g.title}</div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      {g.year} · {(g.genres || []).slice(0, 2).join(" · ")}
                    </div>
                  </div>
                  <div className="hidden sm:flex flex-wrap gap-1 max-w-[200px] justify-end">
                    {(g.platforms || []).slice(0, 3).map((p) => (
                      <span key={p} className="font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 border border-border rounded-sm">{PLATFORM_LABEL[p] || p}</span>
                    ))}
                  </div>
                  <div className="text-right">
                    <div className="flex items-center gap-1 justify-end">
                      <Star size={14} className="fill-primary text-primary" />
                      <span className="font-mono font-bold">{(g.bayesian_score || 0).toFixed(1)}</span>
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground tracking-wider">
                      {g.rating}/100 · {g.rating_count} reviews
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
