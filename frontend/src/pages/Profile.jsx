import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import RankBadge from "@/components/RankBadge";
import ReviewCard from "@/components/ReviewCard";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { PLATFORM_LABEL } from "@/lib/game-data";
import { handleOf, cacheBust } from "@/lib/format";
import { Settings, UserPlus, MessageSquare, Gamepad2, Cpu, Clock, Check, X, Star } from "lucide-react";
import { toast } from "sonner";

const SOCIAL_ICONS = {
  discord: { label: "Discord", color: "text-indigo-400" },
  tiktok: { label: "TikTok", color: "text-pink-400" },
  instagram: { label: "Instagram", color: "text-pink-400" },
  twitch: { label: "Twitch", color: "text-purple-400" },
};

export default function Profile() {
  const { userId } = useParams();
  const { user: me } = useAuth();
  const [profile, setProfile] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.get(`/users/${userId}`).then((r) => setProfile(r.data)).catch(() => setProfile(null));
    api.get(`/users/${userId}/reviews`).then((r) => setReviews(r.data));
  };
  useEffect(load, [userId]);

  const isMe = me?.user_id === userId;
  const status = profile?.friendship_status || "none";

  const sendFriendRequest = async () => {
    setBusy(true);
    try {
      await api.post(`/friends/request/${userId}`);
      toast.success("Pedido de amizade enviado");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
    finally { setBusy(false); }
  };

  const acceptFriend = async () => {
    setBusy(true);
    try {
      await api.post(`/friends/accept/${userId}`);
      toast.success("Amizade aceite");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
    finally { setBusy(false); }
  };

  const removeFriendship = async () => {
    setBusy(true);
    try {
      await api.delete(`/friends/${userId}`);
      toast.success(status === "accepted" ? "Amizade removida" : "Pedido cancelado");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
    finally { setBusy(false); }
  };

  if (!profile) return <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>;

  const fav = profile.prefs?.favorite_game_doc;
  const picVersion = profile.picture || "";
  const avatarSrc = profile.picture ? cacheBust(profile.picture, picVersion.length) : null;

  let actionBtn = null;
  if (isMe) {
    actionBtn = <Button asChild variant="outline" data-testid="profile-edit-btn" className="rounded-sm font-mono uppercase tracking-wider"><Link to="/perfil/editar"><Settings size={14} className="mr-2"/> Editar</Link></Button>;
  } else if (me) {
    if (status === "accepted") {
      actionBtn = (
        <div className="flex flex-col gap-2">
          <span data-testid="profile-status-friends" className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-sm border border-green-500/40 bg-green-500/10 text-green-500 font-mono text-xs uppercase tracking-wider"><Check size={14}/> Amigos</span>
          <Button variant="outline" data-testid="profile-remove-friend" disabled={busy} onClick={removeFriendship} className="rounded-sm font-mono uppercase tracking-wider text-destructive border-destructive/40 hover:bg-destructive/10"><X size={14} className="mr-2"/> Remover amizade</Button>
        </div>
      );
    } else if (status === "pending_sent") {
      actionBtn = (
        <div className="flex flex-col gap-2">
          <span data-testid="profile-status-pending" className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-sm border border-border text-muted-foreground font-mono text-xs uppercase tracking-wider"><Clock size={14}/> Pedido enviado</span>
          <Button variant="outline" data-testid="profile-cancel-request" disabled={busy} onClick={removeFriendship} className="rounded-sm font-mono uppercase tracking-wider"><X size={14} className="mr-2"/> Cancelar</Button>
        </div>
      );
    } else if (status === "pending_received") {
      actionBtn = (
        <div className="flex flex-col gap-2">
          <Button data-testid="profile-accept-btn" disabled={busy} onClick={acceptFriend} className="rounded-sm font-mono uppercase tracking-wider"><Check size={14} className="mr-2"/> Aceitar pedido</Button>
          <Button variant="outline" data-testid="profile-reject-btn" disabled={busy} onClick={removeFriendship} className="rounded-sm font-mono uppercase tracking-wider text-destructive border-destructive/40"><X size={14} className="mr-2"/> Recusar</Button>
        </div>
      );
    } else {
      actionBtn = <Button data-testid="profile-add-friend" disabled={busy} onClick={sendFriendRequest} className="rounded-sm font-mono uppercase tracking-wider"><UserPlus size={14} className="mr-2"/> Adicionar amigo</Button>;
    }
  }

  return (
    <div className="space-y-8">
      <header className="grid md:grid-cols-[auto_1fr_auto] gap-6 items-start gs-card p-6">
        <Avatar className="h-24 w-24 rounded-sm border-2 border-primary">
          <AvatarImage src={avatarSrc} key={avatarSrc} />
          <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-2xl">{(profile.name || "U").slice(0, 2).toUpperCase()}</AvatarFallback>
        </Avatar>

        <div className="space-y-3">
          <div>
            <div className="gs-overline">{handleOf(profile.user_id)}</div>
            <h1 className="font-heading font-black text-3xl uppercase tracking-tight mt-1">{profile.name}</h1>
          </div>
          {profile.bio && <p className="text-sm text-foreground/80 leading-relaxed max-w-2xl">{profile.bio}</p>}
          <RankBadge points={profile.points || 0} />
          <div className="flex flex-wrap gap-3 pt-2 font-mono text-xs">
            <span className="text-muted-foreground">Avaliações: <b className="text-foreground">{profile.stats?.reviews ?? 0}</b></span>
            <span className="text-muted-foreground">Guias: <b className="text-foreground">{profile.stats?.guides ?? 0}</b></span>
            <Link to={`/wishlist/${profile.user_id}`} className="text-muted-foreground hover:text-primary transition-colors">
              Wishlist: <b className="text-foreground">{profile.stats?.wishlist ?? 0}</b>
            </Link>
          </div>
        </div>

        <div className="flex flex-col gap-2">{actionBtn}</div>
      </header>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="gs-card p-5 space-y-3">
          <div className="flex items-center gap-2"><Gamepad2 size={16} className="text-primary"/><div className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Preferências</div></div>
          {fav ? (
            <Link to={`/jogos/${fav.game_id}`} className="flex items-center gap-3 group">
              <img src={fav.cover} alt="" className="w-10 h-12 object-cover rounded-sm" />
              <div>
                <div className="text-xs text-muted-foreground">Jogo favorito</div>
                <div className="font-medium group-hover:text-primary transition-colors">{fav.title}</div>
              </div>
            </Link>
          ) : profile.prefs?.favorite_game ? (
            <div><div className="text-xs text-muted-foreground">Jogo favorito</div><div className="font-medium">{profile.prefs.favorite_game}</div></div>
          ) : (
            <div className="font-mono text-xs text-muted-foreground">Sem jogo favorito</div>
          )}
          <div>
            <div className="text-xs text-muted-foreground mb-1">Plataformas</div>
            <div className="flex flex-wrap gap-1.5">
              {(profile.prefs?.platforms || []).length === 0 ? <span className="font-mono text-xs text-muted-foreground">—</span> :
                profile.prefs.platforms.map((p) => (
                  <span key={p} className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-border rounded-sm">{PLATFORM_LABEL[p] || p}</span>
                ))
              }
            </div>
          </div>
        </div>

        <div className="gs-card p-5 space-y-3">
          <div className="flex items-center gap-2"><Cpu size={16} className="text-primary"/><div className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Specs PC</div></div>
          <div className="font-mono text-xs whitespace-pre-line text-foreground/90 min-h-[60px]">{profile.prefs?.pc_specs || "—"}</div>
        </div>

        <div className="gs-card p-5 space-y-3">
          <div className="flex items-center gap-2"><MessageSquare size={16} className="text-primary"/><div className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Redes</div></div>
          <div className="space-y-2">
            {Object.entries(SOCIAL_ICONS).map(([k, meta]) => {
              const v = profile.social?.[k];
              return (
                <div key={k} className="flex items-center justify-between text-sm">
                  <span className={`font-mono text-xs uppercase tracking-wider ${meta.color}`}>{meta.label}</span>
                  <span className="font-mono text-xs">{v || "—"}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <section className="space-y-4">
        <h2 className="font-heading text-2xl font-bold uppercase tracking-tight">Avaliações</h2>
        {reviews.length === 0 ? (
          <div className="gs-card p-8 text-center font-mono text-sm text-muted-foreground">Sem avaliações ainda.</div>
        ) : (
          <div className="grid md:grid-cols-2 gap-4">
            {reviews.map((r) => <ReviewCard key={r.review_id} review={r} showGame />)}
          </div>
        )}
      </section>
    </div>
  );
}
