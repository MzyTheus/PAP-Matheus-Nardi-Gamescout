import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import RankBadge from "@/components/RankBadge";
import ReviewCard from "@/components/ReviewCard";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { PLATFORM_LABEL } from "@/lib/game-data";
import { Settings, UserPlus, MessageSquare, Gamepad2, Cpu, Star } from "lucide-react";
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

  useEffect(() => {
    api.get(`/users/${userId}`).then((r) => setProfile(r.data)).catch(() => setProfile(null));
    api.get(`/users/${userId}/reviews`).then((r) => setReviews(r.data));
  }, [userId]);

  const isMe = me?.user_id === userId;

  const sendFriendRequest = async () => {
    try {
      await api.post(`/friends/request/${userId}`);
      toast.success("Pedido de amizade enviado");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Erro");
    }
  };

  if (!profile) return <div className="font-mono text-sm text-muted-foreground py-20 text-center tracking-wider">A CARREGAR…</div>;

  return (
    <div className="space-y-8">
      <header className="grid md:grid-cols-[auto_1fr_auto] gap-6 items-start gs-card p-6">
        <Avatar className="h-24 w-24 rounded-sm border-2 border-primary">
          <AvatarImage src={profile.picture} />
          <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-2xl">{(profile.name || "U").slice(0, 2).toUpperCase()}</AvatarFallback>
        </Avatar>

        <div className="space-y-3">
          <div>
            <div className="gs-overline">@{profile.user_id}</div>
            <h1 className="font-heading font-black text-3xl uppercase tracking-tight mt-1">{profile.name}</h1>
          </div>
          {profile.bio && <p className="text-sm text-foreground/80 leading-relaxed max-w-2xl">{profile.bio}</p>}
          <RankBadge points={profile.points || 0} />
          <div className="flex flex-wrap gap-3 pt-2 font-mono text-xs">
            <span className="text-muted-foreground">Avaliações: <b className="text-foreground">{profile.stats?.reviews ?? 0}</b></span>
            <span className="text-muted-foreground">Guias: <b className="text-foreground">{profile.stats?.guides ?? 0}</b></span>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          {isMe ? (
            <Button asChild variant="outline" data-testid="profile-edit-btn" className="rounded-sm font-mono uppercase tracking-wider"><Link to="/perfil/editar"><Settings size={14} className="mr-2"/> Editar</Link></Button>
          ) : me ? (
            <Button data-testid="profile-add-friend" onClick={sendFriendRequest} className="rounded-sm font-mono uppercase tracking-wider"><UserPlus size={14} className="mr-2"/> Adicionar</Button>
          ) : null}
        </div>
      </header>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="gs-card p-5 space-y-3">
          <div className="flex items-center gap-2"><Gamepad2 size={16} className="text-primary"/><div className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Preferências</div></div>
          {profile.prefs?.favorite_game ? (
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
