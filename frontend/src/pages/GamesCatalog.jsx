import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import GameCard from "@/components/GameCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { GENRES, PLATFORMS } from "@/lib/game-data";
import { Search } from "lucide-react";

export default function GamesCatalog() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const genre = params.get("genre") || "";
  const platform = params.get("platform") || "";

  const [search, setSearch] = useState(q);
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { setSearch(q); }, [q]);

  useEffect(() => {
    setLoading(true);
    const sp = {};
    if (q) sp.q = q;
    if (genre) sp.genre = genre;
    if (platform) sp.platform = platform;
    api.get("/games", { params: sp }).then((r) => setList(r.data)).finally(() => setLoading(false));
  }, [q, genre, platform]);

  const setParam = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };

  const onSearch = (e) => {
    e.preventDefault();
    setParam("q", search.trim());
  };

  return (
    <div className="space-y-8">
      <div>
        <div className="gs-overline">Catálogo</div>
        <h1 className="font-heading font-black text-3xl sm:text-4xl uppercase tracking-tight mt-1">Procura o teu próximo jogo</h1>
      </div>

      <form onSubmit={onSearch} className="flex gap-2 max-w-xl">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input data-testid="catalog-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Procurar…" className="pl-9 h-11 rounded-sm" />
        </div>
        <Button type="submit" data-testid="catalog-search-btn" className="rounded-sm font-mono uppercase tracking-wider">Pesquisar</Button>
      </form>

      <div className="space-y-4">
        <div>
          <div className="font-mono text-xs uppercase tracking-widest text-muted-foreground mb-2">Géneros</div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setParam("genre", "")} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${!genre ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>Todos</button>
            {GENRES.map((g) => (
              <button key={g} data-testid={`genre-${g}`} onClick={() => setParam("genre", g)} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${genre === g ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>{g}</button>
            ))}
          </div>
        </div>
        <div>
          <div className="font-mono text-xs uppercase tracking-widest text-muted-foreground mb-2">Plataforma</div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setParam("platform", "")} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${!platform ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>Todas</button>
            {PLATFORMS.map((p) => (
              <button key={p.id} onClick={() => setParam("platform", p.id)} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${platform === p.id ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>{p.label}</button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>
      ) : list.length === 0 ? (
        <div className="gs-card p-12 text-center">
          <div className="font-heading text-xl uppercase tracking-tight">Nada por aqui</div>
          <div className="font-mono text-sm text-muted-foreground mt-2">Tenta outro filtro ou pesquisa.</div>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {list.map((g) => (<GameCard key={g.game_id} game={g} />))}
        </div>
      )}
    </div>
  );
}
