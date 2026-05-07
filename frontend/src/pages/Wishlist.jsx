import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import GameCard from "@/components/GameCard";
import { Heart, Bookmark } from "lucide-react";

export default function Wishlist() {
  const { userId } = useParams();
  const { user } = useAuth();
  const [list, setList] = useState(null);
  const [owner, setOwner] = useState(null);
  const targetId = userId || user?.user_id;

  useEffect(() => {
    if (!targetId) return;
    api.get(`/users/${targetId}/wishlist`).then((r) => setList(r.data)).catch(() => setList([]));
    if (userId) {
      api.get(`/users/${userId}`).then((r) => setOwner(r.data)).catch(() => {});
    } else {
      setOwner(user);
    }
  }, [targetId, userId, user]);

  if (!user && !userId) {
    return (
      <div className="text-center py-20 space-y-3">
        <Heart size={32} className="mx-auto text-primary" />
        <h1 className="font-heading font-black text-2xl uppercase tracking-tight">Inicia sessão</h1>
        <Link to="/login" className="font-mono text-xs uppercase tracking-wider text-primary">Entrar →</Link>
      </div>
    );
  }

  const isMine = user && targetId === user.user_id;

  if (list === null) return <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>;

  return (
    <div className="space-y-8">
      <header>
        <div className="gs-overline flex items-center gap-1.5"><Bookmark size={12}/> {isMine ? "A tua coleção" : `Coleção de ${owner?.name || ""}`}</div>
        <h1 className="font-heading font-black text-3xl sm:text-5xl uppercase tracking-tighter mt-1">Wishlist</h1>
        <p className="text-sm text-muted-foreground mt-2">
          {isMine
            ? "Os jogos que queres jogar. Marca-os na lista e a página Descobrir vai inspirar-se neles."
            : `Os jogos na lista de ${owner?.name || "este utilizador"}.`}
        </p>
      </header>

      {list.length === 0 ? (
        <div className="gs-card p-12 text-center space-y-3">
          <Heart size={32} className="mx-auto text-primary" />
          <div className="font-heading text-xl uppercase tracking-tight">Nada na wishlist</div>
          <div className="font-mono text-sm text-muted-foreground">
            {isMine ? <>Carrega no <Heart size={12} className="inline mb-0.5"/> em qualquer jogo do <Link to="/jogos" className="text-primary underline-offset-4 hover:underline">catálogo</Link>.</> : "Sem jogos guardados."}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {list.map((g) => (<GameCard key={g.game_id} game={g} />))}
        </div>
      )}
    </div>
  );
}
