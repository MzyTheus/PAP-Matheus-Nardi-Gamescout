import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";

const CATEGORIES = [
  { id: "dica", label: "Dica" },
  { id: "tutorial", label: "Tutorial" },
  { id: "como-zerar", label: "Como zerar" },
  { id: "estrategia", label: "Estratégia" },
  { id: "macete", label: "Macete" },
];

export default function GuideForm() {
  const { gameId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [game, setGame] = useState(null);
  const [form, setForm] = useState({ title: "", content: "", category: "dica" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { api.get(`/games/${gameId}`).then((r) => setGame(r.data)); }, [gameId]);

  if (user && user.points < 50) {
    return (
      <div className="max-w-xl mx-auto py-20 text-center space-y-3">
        <div className="font-heading font-black text-3xl uppercase tracking-tight text-primary">Acesso bloqueado</div>
        <p className="text-muted-foreground">Precisa do nível <b>Explorador</b> (50 pts) para criar guias. Avalia mais jogos para subir!</p>
        <Button asChild variant="outline" className="rounded-sm font-mono uppercase tracking-wider"><Link to={`/jogos/${gameId}`}>Voltar ao jogo</Link></Button>
      </div>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post(`/games/${gameId}/guides`, form);
      toast.success("Guia publicado!");
      nav(`/jogos/${gameId}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <Link to={`/jogos/${gameId}`} className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:text-primary"><ArrowLeft size={14}/> Voltar</Link>
      <div>
        <div className="gs-overline">Novo guia</div>
        <h1 className="font-heading font-black text-3xl uppercase tracking-tight mt-1">{game?.title}</h1>
      </div>
      <form onSubmit={submit} className="gs-card p-6 space-y-5">
        <div className="space-y-1.5">
          <Label className="font-mono uppercase text-[11px] tracking-wider">Categoria</Label>
          <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
            <SelectTrigger data-testid="guide-category" className="rounded-sm"><SelectValue /></SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="font-mono uppercase text-[11px] tracking-wider">Título</Label>
          <Input data-testid="guide-title" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="rounded-sm" />
        </div>
        <div className="space-y-1.5">
          <Label className="font-mono uppercase text-[11px] tracking-wider">Conteúdo (mín. 20 caracteres)</Label>
          <Textarea data-testid="guide-content" required minLength={20} rows={10} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} className="rounded-sm" />
        </div>
        <div className="flex justify-end">
          <Button type="submit" disabled={submitting} data-testid="guide-submit" className="rounded-sm font-mono uppercase tracking-wider">{submitting ? "A publicar…" : "Publicar guia"}</Button>
        </div>
      </form>
    </div>
  );
}
