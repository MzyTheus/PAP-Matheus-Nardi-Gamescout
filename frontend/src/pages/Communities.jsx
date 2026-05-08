import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Users, Plus, Search } from "lucide-react";
import { toast } from "sonner";

export default function Communities() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [list, setList] = useState([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });

  const load = () => {
    api.get("/communities", { params: q ? { q } : {} }).then((r) => setList(r.data || []));
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [q]);

  const onCreate = async (e) => {
    e.preventDefault();
    if (!user) { nav("/login"); return; }
    if (form.name.trim().length < 3) { toast.error("Nome demasiado curto"); return; }
    setCreating(true);
    try {
      const { data } = await api.post("/communities", { name: form.name.trim(), description: form.description.trim() });
      toast.success("Comunidade criada");
      setOpen(false);
      setForm({ name: "", description: "" });
      nav(`/comunidades/${data.community_id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro");
    } finally {
      setCreating(false);
    }
  };

  const join = async (id) => {
    if (!user) { nav("/login"); return; }
    try {
      await api.post(`/communities/${id}/join`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="gs-overline flex items-center gap-1.5"><Users size={12}/> Espaços públicos</div>
          <h1 className="font-heading font-black text-3xl sm:text-5xl uppercase tracking-tighter mt-1">Comunidades</h1>
          <p className="text-sm text-muted-foreground mt-2 max-w-xl">Cria ou junta-te a grupos públicos para conversar sobre os teus jogos favoritos.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="community-create-btn" className="rounded-sm font-mono uppercase tracking-wider"><Plus size={14} className="mr-1"/> Criar</Button>
          </DialogTrigger>
          <DialogContent className="rounded-sm">
            <DialogHeader><DialogTitle>Nova comunidade</DialogTitle></DialogHeader>
            <form onSubmit={onCreate} className="space-y-4">
              <div className="space-y-1.5">
                <Label className="font-mono uppercase text-xs tracking-widest text-muted-foreground">Nome *</Label>
                <Input data-testid="community-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={40} className="rounded-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="font-mono uppercase text-xs tracking-widest text-muted-foreground">Descrição</Label>
                <Textarea data-testid="community-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={240} rows={3} className="rounded-sm" />
              </div>
              <DialogFooter>
                <Button type="submit" data-testid="community-submit" disabled={creating} className="rounded-sm font-mono uppercase tracking-wider">{creating ? "A criar…" : "Criar"}</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </header>

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input data-testid="community-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Procurar comunidades…" className="pl-9 rounded-sm" />
      </div>

      {list.length === 0 ? (
        <div className="gs-card p-12 text-center">
          <Users size={32} className="mx-auto mb-3 opacity-40" />
          <div className="font-heading text-xl uppercase tracking-tight">Nenhuma comunidade ainda</div>
          <div className="text-sm text-muted-foreground mt-2">Sê o primeiro a criar uma.</div>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {list.map((c) => (
            <article key={c.community_id} className="gs-card p-5 flex flex-col gap-3" data-testid={`community-${c.community_id}`}>
              <Link to={`/comunidades/${c.community_id}`} className="space-y-1">
                <div className="font-heading font-bold text-lg uppercase tracking-tight hover:text-primary transition-colors line-clamp-1">{c.name}</div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{c.members_count} {c.members_count === 1 ? "membro" : "membros"}</div>
              </Link>
              {c.description && <p className="text-sm text-foreground/80 line-clamp-3">{c.description}</p>}
              <div className="mt-auto pt-2">
                {c.is_member ? (
                  <Button variant="outline" size="sm" onClick={() => nav(`/comunidades/${c.community_id}`)} data-testid={`community-open-${c.community_id}`} className="rounded-sm w-full font-mono uppercase tracking-wider">Abrir</Button>
                ) : (
                  <Button size="sm" onClick={() => join(c.community_id)} data-testid={`community-join-${c.community_id}`} className="rounded-sm w-full font-mono uppercase tracking-wider">Juntar-me</Button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
