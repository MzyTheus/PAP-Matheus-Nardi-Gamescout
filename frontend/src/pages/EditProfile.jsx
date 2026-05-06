import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PLATFORMS } from "@/lib/game-data";
import GamePicker from "@/components/GamePicker";
import { toast } from "sonner";
import { Save, ArrowLeft } from "lucide-react";

export default function EditProfile() {
  const { user, refresh } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState(null);
  const [favGame, setFavGame] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user) {
      const prefs = user.prefs || {};
      setForm({
        name: user.name || "",
        bio: user.bio || "",
        picture: user.picture || "",
        social: { discord: "", tiktok: "", instagram: "", twitch: "", ...(user.social || {}) },
        prefs: { favorite_game: "", favorite_game_id: null, pc_specs: "", platforms: [], ...prefs },
      });
      // Load favorite game doc if id exists
      if (prefs.favorite_game_id) {
        api.get(`/games/${prefs.favorite_game_id}`).then((r) => {
          setFavGame({ game_id: r.data.game_id, title: r.data.title, cover: r.data.cover });
        }).catch(() => {});
      }
    }
  }, [user]);

  if (!form) return null;

  const togglePlatform = (id) => {
    setForm((f) => {
      const has = f.prefs.platforms.includes(id);
      return { ...f, prefs: { ...f.prefs, platforms: has ? f.prefs.platforms.filter((p) => p !== id) : [...f.prefs.platforms, id] } };
    });
  };

  const onSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        prefs: {
          ...form.prefs,
          favorite_game: favGame?.title || null,
          favorite_game_id: favGame?.game_id || null,
        },
      };
      await api.patch("/users/me", payload);
      await refresh();
      toast.success("Perfil atualizado");
      nav(`/perfil/${user.user_id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao guardar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <Link to={`/perfil/${user.user_id}`} className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:text-primary"><ArrowLeft size={14}/> Voltar</Link>
      <div>
        <div className="gs-overline">Editar</div>
        <h1 className="font-heading font-black text-3xl uppercase tracking-tight mt-1">O teu perfil</h1>
      </div>

      <form onSubmit={onSave} className="space-y-8">
        <section className="gs-card p-6 space-y-4">
          <h2 className="font-mono uppercase text-xs tracking-widest text-primary">Identidade</h2>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="font-mono uppercase text-[11px] tracking-wider">Nome</Label>
              <Input data-testid="edit-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-sm" />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono uppercase text-[11px] tracking-wider">URL da foto de perfil</Label>
              <Input data-testid="edit-picture" placeholder="https://..." value={form.picture} onChange={(e) => setForm({ ...form, picture: e.target.value })} className="rounded-sm" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono uppercase text-[11px] tracking-wider">Biografia</Label>
            <Textarea data-testid="edit-bio" rows={4} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} className="rounded-sm" />
          </div>
        </section>

        <section className="gs-card p-6 space-y-4">
          <h2 className="font-mono uppercase text-xs tracking-widest text-primary">Preferências de jogo</h2>
          <div className="space-y-1.5">
            <Label className="font-mono uppercase text-[11px] tracking-wider">Jogo favorito</Label>
            <GamePicker value={favGame} onChange={setFavGame} testId="edit-fav-game" />
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono uppercase text-[11px] tracking-wider">Plataformas</Label>
            <div className="flex flex-wrap gap-2">
              {PLATFORMS.map((p) => (
                <button type="button" key={p.id} data-testid={`edit-platform-${p.id}`} onClick={() => togglePlatform(p.id)} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${form.prefs.platforms.includes(p.id) ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>{p.label}</button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono uppercase text-[11px] tracking-wider">Specs do PC (opcional)</Label>
            <Textarea data-testid="edit-pc-specs" rows={3} placeholder="CPU · GPU · RAM..." value={form.prefs.pc_specs || ""} onChange={(e) => setForm({ ...form, prefs: { ...form.prefs, pc_specs: e.target.value } })} className="rounded-sm font-mono text-sm" />
          </div>
        </section>

        <section className="gs-card p-6 space-y-4">
          <h2 className="font-mono uppercase text-xs tracking-widest text-primary">Redes sociais</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {[["discord", "Discord (user#tag)"], ["tiktok", "TikTok (@user)"], ["instagram", "Instagram (@user)"], ["twitch", "Twitch (canal)"]].map(([k, label]) => (
              <div key={k} className="space-y-1.5">
                <Label className="font-mono uppercase text-[11px] tracking-wider">{label}</Label>
                <Input data-testid={`edit-social-${k}`} value={form.social[k] || ""} onChange={(e) => setForm({ ...form, social: { ...form.social, [k]: e.target.value } })} className="rounded-sm" />
              </div>
            ))}
          </div>
        </section>

        <div className="flex justify-end">
          <Button type="submit" disabled={saving} data-testid="edit-save-btn" className="rounded-sm font-mono uppercase tracking-wider"><Save size={14} className="mr-2"/>{saving ? "A guardar…" : "Guardar"}</Button>
        </div>
      </form>
    </div>
  );
}
