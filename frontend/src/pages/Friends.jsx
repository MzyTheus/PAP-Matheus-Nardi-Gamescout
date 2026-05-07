import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Search, UserPlus, Check, Users, UserMinus } from "lucide-react";

export default function Friends() {
  const [friends, setFriends] = useState([]);
  const [requests, setRequests] = useState([]);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);

  const load = () => {
    api.get("/friends").then((r) => setFriends(r.data));
    api.get("/friends/requests").then((r) => setRequests(r.data));
  };
  useEffect(load, []);

  const onSearch = async (e) => {
    e.preventDefault();
    if (search.trim().length < 2) { setResults([]); return; }
    try {
      const { data } = await api.get("/users/search", { params: { q: search.trim() } });
      setResults(data);
    } catch (e) { /* ignore */ }
  };

  const sendReq = async (uid) => {
    try { await api.post(`/friends/request/${uid}`); toast.success("Pedido enviado"); }
    catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };
  const accept = async (uid) => {
    try { await api.post(`/friends/accept/${uid}`); toast.success("Amizade aceite"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  return (
    <div className="space-y-8">
      <div>
        <div className="gs-overline">Comunidade</div>
        <h1 className="font-heading font-black text-3xl sm:text-4xl uppercase tracking-tight mt-1">Amigos</h1>
      </div>

      <section className="gs-card p-6 space-y-4">
        <h2 className="font-mono uppercase text-xs tracking-widest text-primary">Encontrar jogadores</h2>
        <form onSubmit={onSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input data-testid="friend-search" placeholder="Procurar pelo nome…" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9 rounded-sm" />
          </div>
          <Button type="submit" data-testid="friend-search-btn" className="rounded-sm font-mono uppercase tracking-wider">Procurar</Button>
        </form>
        {results.length > 0 && (
          <div className="grid sm:grid-cols-2 gap-3">
            {results.map((u) => (
              <div key={u.user_id} className="flex items-center gap-3 p-3 border border-border rounded-sm">
                <Avatar className="h-9 w-9 rounded-sm">
                  <AvatarImage src={u.picture} />
                  <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-xs">{(u.name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <Link to={`/perfil/${u.user_id}`} className="font-semibold hover:text-primary">{u.name}</Link>
                  <div className="font-mono text-[10px] uppercase text-muted-foreground tracking-wider">{u.points || 0} pts</div>
                </div>
                <Button size="sm" data-testid={`add-${u.user_id}`} onClick={() => sendReq(u.user_id)} className="rounded-sm"><UserPlus size={14}/></Button>
              </div>
            ))}
          </div>
        )}
      </section>

      {requests.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-mono uppercase text-xs tracking-widest text-primary">Pedidos pendentes ({requests.length})</h2>
          <div className="grid sm:grid-cols-2 gap-3">
            {requests.map((req) => {
              const u = req.from_user;
              return (
                <div key={u.user_id} data-testid={`req-${u.user_id}`} className="flex items-center gap-3 p-3 gs-card">
                  <Avatar className="h-9 w-9 rounded-sm">
                    <AvatarImage src={u.picture} />
                    <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-xs">{(u.name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <Link to={`/perfil/${u.user_id}`} className="font-semibold hover:text-primary">{u.name}</Link>
                  </div>
                  <Button size="sm" data-testid={`accept-${u.user_id}`} onClick={() => accept(u.user_id)} className="rounded-sm"><Check size={14}/></Button>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="font-mono uppercase text-xs tracking-widest text-primary">Os teus amigos ({friends.length})</h2>
        {friends.length === 0 ? (
          <div className="gs-card p-12 text-center">
            <Users size={32} className="mx-auto text-primary mb-3" />
            <div className="font-heading text-xl uppercase tracking-tight">Ainda sem amigos</div>
            <div className="font-mono text-sm text-muted-foreground mt-2">Encontra jogadores acima para começar.</div>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
            {friends.map((u) => (
              <div key={u.user_id} className="gs-card p-4 flex items-center gap-3">
                <Link to={`/perfil/${u.user_id}`} className="flex items-center gap-3 flex-1 min-w-0">
                  <Avatar className="h-10 w-10 rounded-sm">
                    <AvatarImage src={u.picture} />
                    <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono">{(u.name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0">
                    <div className="font-semibold truncate">{u.name}</div>
                    <div className="font-mono text-[10px] uppercase text-muted-foreground tracking-wider">{u.points || 0} pts</div>
                  </div>
                </Link>
                <Button
                  size="sm"
                  variant="outline"
                  data-testid={`unfriend-${u.user_id}`}
                  onClick={async () => {
                    try { await api.delete(`/friends/${u.user_id}`); toast.success("Amizade removida"); load(); }
                    catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
                  }}
                  className="rounded-sm text-destructive border-destructive/40 hover:bg-destructive/10"
                  title="Remover amizade"
                >
                  <UserMinus size={14} />
                </Button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
