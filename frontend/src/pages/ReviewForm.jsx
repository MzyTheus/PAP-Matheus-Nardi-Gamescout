import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import StarRating from "@/components/StarRating";
import { PLATFORMS } from "@/lib/game-data";
import { toast } from "sonner";
import { ArrowLeft, ThumbsUp, ThumbsDown } from "lucide-react";

const CategoryRow = ({ label, value, set, testId }) => (
  <div className="flex items-center justify-between gap-4 py-3 border-b border-border last:border-0">
    <Label className="font-mono uppercase text-xs tracking-widest text-muted-foreground">{label}</Label>
    <StarRating testId={testId} value={value || 0} max={10} size={18} onChange={set} />
  </div>
);

const EMPTY = {
  rating: 0, hours_played: "",
  graphics: 0, story: 0, tutorial: 0, gameplay: 0,
  recommends: null, platform: "", note: "",
};

export default function ReviewForm() {
  const { gameId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [game, setGame] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [existingReviewId, setExistingReviewId] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/games/${gameId}`).then((r) => setGame(r.data));
    if (user) {
      api.get(`/games/${gameId}/reviews`).then((r) => {
        const mine = r.data.find((rv) => rv.user_id === user.user_id);
        if (mine) {
          setExistingReviewId(mine.review_id);
          setForm({
            rating: mine.rating || 0,
            hours_played: mine.hours_played ?? "",
            graphics: mine.graphics || 0,
            story: mine.story || 0,
            tutorial: mine.tutorial || 0,
            gameplay: mine.gameplay || 0,
            recommends: mine.recommends ?? null,
            platform: mine.platform || "",
            note: mine.note || "",
          });
        }
      });
    }
  }, [gameId, user]);

  const isComplete =
    form.rating > 0 && form.hours_played !== "" && form.graphics > 0 && form.story > 0 &&
    form.tutorial > 0 && form.gameplay > 0 && form.recommends !== null && form.platform &&
    (form.note || "").trim().length >= 10;

  const submit = async (e) => {
    e.preventDefault();
    if (!form.rating) { toast.error("Dá uma nota geral primeiro"); return; }
    setSubmitting(true);
    try {
      const payload = { ...form };
      payload.hours_played = form.hours_played === "" ? null : Number(form.hours_played);
      ["graphics", "story", "tutorial", "gameplay"].forEach((k) => { if (!payload[k]) payload[k] = null; });
      if (!payload.platform) payload.platform = null;
      if (existingReviewId) {
        await api.patch(`/reviews/${existingReviewId}`, payload);
        toast.success("Avaliação atualizada");
      } else {
        const { data } = await api.post(`/games/${gameId}/reviews`, payload);
        toast.success(data.is_complete ? "Avaliação completa! +50 pts" : "Avaliação publicada (+25 pts)");
      }
      nav(`/jogos/${gameId}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao publicar");
    } finally {
      setSubmitting(false);
    }
  };

  if (!game) return null;

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <Link to={`/jogos/${gameId}`} className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:text-primary"><ArrowLeft size={14}/> Voltar a {game.title}</Link>

      <div>
        <div className="gs-overline">{existingReviewId ? "Editar avaliação" : "Avaliar"}</div>
        <h1 className="font-heading font-black text-3xl uppercase tracking-tight mt-1">{game.title}</h1>
      </div>

      <div className={`gs-card p-3 font-mono text-xs flex items-center gap-2 ${isComplete ? "border-green-500/40 text-green-500" : "text-muted-foreground"}`}>
        <span className="w-2 h-2 rounded-full" style={{ background: isComplete ? "#22c55e" : "#888" }} />
        {isComplete ? "AVALIAÇÃO COMPLETA · +50 PTS" : "PARCIAL · +25 PTS · COMPLETA TODOS OS CAMPOS PARA +50 PTS"}
      </div>

      <form onSubmit={submit} className="space-y-6">
        <section className="gs-card p-6 space-y-3">
          <Label className="font-mono uppercase text-xs tracking-widest text-primary">Nota geral *</Label>
          <StarRating testId="review-overall" value={form.rating} onChange={(v) => setForm({ ...form, rating: v })} size={28} />
        </section>

        <section className="gs-card p-6 space-y-3">
          <Label className="font-mono uppercase text-xs tracking-widest text-primary">Horas jogadas</Label>
          <Input data-testid="review-hours" type="number" min={0} placeholder="Ex: 42" value={form.hours_played} onChange={(e) => setForm({ ...form, hours_played: e.target.value })} className="rounded-sm font-mono w-32" />
        </section>

        <section className="gs-card p-6">
          <Label className="font-mono uppercase text-xs tracking-widest text-primary mb-2 block">Categorias (1–10)</Label>
          <CategoryRow label="Gráficos" testId="cat-graphics" value={form.graphics} set={(v) => setForm({ ...form, graphics: v })} />
          <CategoryRow label="História" testId="cat-story" value={form.story} set={(v) => setForm({ ...form, story: v })} />
          <CategoryRow label="Tutorial" testId="cat-tutorial" value={form.tutorial} set={(v) => setForm({ ...form, tutorial: v })} />
          <CategoryRow label="Jogabilidade" testId="cat-gameplay" value={form.gameplay} set={(v) => setForm({ ...form, gameplay: v })} />
        </section>

        <section className="gs-card p-6 space-y-3">
          <Label className="font-mono uppercase text-xs tracking-widest text-primary">Recomenda?</Label>
          <div className="flex gap-2">
            <button type="button" data-testid="review-recommend-yes" onClick={() => setForm({ ...form, recommends: true })} className={`flex-1 inline-flex items-center justify-center gap-2 px-4 py-3 border rounded-sm font-mono uppercase tracking-wider text-sm transition ${form.recommends === true ? "bg-green-500/10 border-green-500 text-green-500" : "border-border hover:border-primary"}`}><ThumbsUp size={14}/> Sim</button>
            <button type="button" data-testid="review-recommend-no" onClick={() => setForm({ ...form, recommends: false })} className={`flex-1 inline-flex items-center justify-center gap-2 px-4 py-3 border rounded-sm font-mono uppercase tracking-wider text-sm transition ${form.recommends === false ? "bg-red-500/10 border-red-500 text-red-400" : "border-border hover:border-primary"}`}><ThumbsDown size={14}/> Não</button>
          </div>
        </section>

        <section className="gs-card p-6 space-y-3">
          <Label className="font-mono uppercase text-xs tracking-widest text-primary">Plataforma onde jogou</Label>
          <div className="flex flex-wrap gap-2">
            {PLATFORMS.map((p) => (
              <button type="button" key={p.id} data-testid={`review-platform-${p.id}`} onClick={() => setForm({ ...form, platform: p.id })} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${form.platform === p.id ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>{p.label}</button>
            ))}
          </div>
        </section>

        <section className="gs-card p-6 space-y-3">
          <Label className="font-mono uppercase text-xs tracking-widest text-primary">Observação</Label>
          <Textarea data-testid="review-note" rows={6} placeholder="Conta-nos a tua experiência..." value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className="rounded-sm" />
          <div className="font-mono text-[10px] text-muted-foreground tracking-wider">≥ 10 caracteres para contar como completa</div>
        </section>

        <div className="flex justify-end">
          <Button type="submit" disabled={submitting || !form.rating} data-testid="review-submit" className="rounded-sm font-mono uppercase tracking-wider">
            {submitting ? "A enviar…" : existingReviewId ? "Atualizar avaliação" : "Publicar avaliação"}
          </Button>
        </div>
      </form>
    </div>
  );
}
