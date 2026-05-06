import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Search, X } from "lucide-react";

/**
 * Searchable game picker — type to search backend catalog, click to select.
 * Props:
 *   value: { game_id, title, cover } | null
 *   onChange: (game) => void
 */
export default function GamePicker({ value, onChange, testId = "game-picker" }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    function onClickOutside(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setResults([]);
      return;
    }
    const id = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await api.get("/games", { params: { q: query.trim(), limit: 8 } });
        setResults(data);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 220);
    return () => clearTimeout(id);
  }, [query]);

  if (value) {
    return (
      <div className="flex items-center gap-3 p-2 border border-border rounded-sm bg-surface" data-testid={`${testId}-selected`}>
        <img src={value.cover} alt={value.title} className="w-10 h-12 object-cover rounded-sm" />
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{value.title}</div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Jogo favorito</div>
        </div>
        <button type="button" data-testid={`${testId}-clear`} onClick={() => { onChange(null); setQuery(""); }} className="p-2 text-muted-foreground hover:text-destructive transition-colors">
          <X size={14} />
        </button>
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="relative">
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          data-testid={testId}
          placeholder="Procurar jogo no catálogo…"
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          className="pl-9 rounded-sm"
          autoComplete="off"
        />
      </div>
      {open && query.trim().length >= 2 && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-popover border border-border rounded-sm shadow-lg max-h-80 overflow-auto">
          {loading ? (
            <div className="p-3 font-mono text-xs text-muted-foreground tracking-wider uppercase">A procurar…</div>
          ) : results.length === 0 ? (
            <div className="p-3 font-mono text-xs text-muted-foreground tracking-wider uppercase">Nenhum jogo encontrado</div>
          ) : (
            results.map((g) => (
              <button
                key={g.game_id}
                type="button"
                data-testid={`${testId}-item-${g.game_id}`}
                onClick={() => { onChange({ game_id: g.game_id, title: g.title, cover: g.cover }); setOpen(false); setQuery(""); }}
                className="w-full flex items-center gap-3 p-2 hover:bg-surface-hover text-left transition-colors"
              >
                <img src={g.cover} alt="" className="w-8 h-10 object-cover rounded-sm" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{g.title}</div>
                  <div className="font-mono text-[10px] text-muted-foreground tracking-wider">{g.year}</div>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
