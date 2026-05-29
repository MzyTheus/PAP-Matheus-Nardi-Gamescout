import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { ShieldAlert, Search, Ban, Mail, Trash2, Star, Users, Gamepad2, MessageSquare, FileText } from "lucide-react";
import { toast } from "sonner";

function StatTile({ label, value, icon }) {
  return (
    <div className="gs-card p-4 flex items-start justify-between gap-2">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
        <div className="font-heading font-black text-2xl mt-1">{value ?? "—"}</div>
      </div>
      <div className="text-primary">{icon}</div>
    </div>
  );
}

export default function AdminDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [q, setQ] = useState("");
  const [target, setTarget] = useState(null);
  const [warnDialog, setWarnDialog] = useState(false);
  const [suspendDialog, setSuspendDialog] = useState(false);
  const [warn, setWarn] = useState({ message: "" });
  const [susp, setSusp] = useState({ days: 7, reason: "" });

  const load = () => {
    api.get("/admin/stats").then((r) => setStats(r.data)).catch(() => null);
    api.get("/admin/users", { params: q ? { q } : {} }).then((r) => setUsers(r.data || [])).catch(() => null);
  };

  useEffect(() => { if (user?.role === "admin") load(); /* eslint-disable-next-line */ }, [user, q]);

  if (!user) return null;
  if (user.role !== "admin") {
    return (
      <div className="gs-card p-12 text-center space-y-2">
        <ShieldAlert size={32} className="mx-auto text-destructive" />
        <div className="font-heading text-xl uppercase tracking-tight">Acesso negado</div>
        <div className="text-sm text-muted-foreground">Esta área é apenas para administradores.</div>
        <Button asChild variant="outline" className="rounded-sm mt-2"><Link to="/">Voltar</Link></Button>
      </div>
    );
  }

  const submitWarn = async () => {
    if (!target || warn.message.trim().length < 2) return;
    try {
      await api.post(`/admin/users/${target.user_id}/warn`, { message: warn.message.trim() });
      toast.success("Aviso enviado");
      setWarnDialog(false); setWarn({ message: "" });
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  const submitSuspend = async () => {
    if (!target) return;
    try {
      await api.post(`/admin/users/${target.user_id}/suspend`, { days: Number(susp.days), reason: susp.reason });
      toast.success(`Suspenso por ${susp.days} dias`);
      setSuspendDialog(false); setSusp({ days: 7, reason: "" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  const unsuspend = async (u) => {
    try {
      await api.post(`/admin/users/${u.user_id}/unsuspend`);
      toast.success("Suspensão removida");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  return (
    <div className="space-y-8">
      <header>
        <div className="gs-overline flex items-center gap-1.5"><ShieldAlert size={12}/> Painel restrito</div>
        <h1 className="font-heading font-black text-3xl sm:text-5xl uppercase tracking-tighter mt-1">Administração</h1>
        <p className="text-sm text-muted-foreground mt-2">Modera utilizadores, conteúdos e jogos da plataforma.</p>
      </header>

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Utilizadores" value={stats?.users} icon={<Users size={18}/>} />
        <StatTile label="Jogos" value={stats?.games} icon={<Gamepad2 size={18}/>} />
        <StatTile label="Reviews" value={stats?.reviews} icon={<Star size={18}/>} />
        <StatTile label="Guias" value={stats?.guides} icon={<FileText size={18}/>} />
        <StatTile label="Comunidades" value={stats?.communities} icon={<Users size={18}/>} />
        <StatTile label="Mensagens" value={stats?.messages} icon={<MessageSquare size={18}/>} />
        <StatTile label="Suspensos" value={stats?.suspended_users} icon={<Ban size={18}/>} />
      </section>

      <section className="space-y-4" data-testid="admin-users">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="font-heading font-bold text-xl uppercase tracking-tight">Utilizadores</h2>
          <div className="relative max-w-xs flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input data-testid="admin-search-users" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Procurar nome / email / id" className="pl-9 rounded-sm" />
          </div>
        </div>

        <div className="gs-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-muted/30">
              <tr className="text-left font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                <th className="px-3 py-2">Utilizador</th>
                <th className="px-3 py-2">Email</th>
                <th className="px-3 py-2">Pts</th>
                <th className="px-3 py-2">Função</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2 text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const suspended = u.suspended_until && new Date(u.suspended_until) > new Date();
                return (
                  <tr key={u.user_id} className="border-b border-border last:border-0 hover:bg-muted/20" data-testid={`admin-user-row-${u.user_id}`}>
                    <td className="px-3 py-2">
                      <Link to={`/perfil/${u.user_id}`} className="flex items-center gap-2 hover:text-primary">
                        <Avatar className="h-7 w-7 rounded-sm">
                          <AvatarImage src={u.picture} />
                          <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-[10px]">{(u.name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <div className="text-sm font-medium truncate">{u.name}</div>
                          <div className="font-mono text-[10px] text-muted-foreground truncate">@{u.user_id.replace(/^user_/, "")}</div>
                        </div>
                      </Link>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{u.email}</td>
                    <td className="px-3 py-2 font-mono text-xs">{u.points || 0}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 text-[10px] uppercase tracking-wider rounded-sm ${u.role === "admin" ? "bg-primary/10 text-primary border border-primary/40" : "border border-border text-muted-foreground"}`}>{u.role || "user"}</span>
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {suspended ? (
                        <span className="text-destructive">Suspenso até {new Date(u.suspended_until).toLocaleDateString("pt-PT")}</span>
                      ) : !u.email_verified && u.auth_provider === "email" ? (
                        <span className="text-yellow-500">Não verificado</span>
                      ) : (
                        <span className="text-green-500">Ativo</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right space-x-1 whitespace-nowrap">
                      <Button size="sm" variant="ghost" data-testid={`admin-warn-${u.user_id}`} onClick={() => { setTarget(u); setWarnDialog(true); }} title="Avisar"><Mail size={14}/></Button>
                      {suspended ? (
                        <Button size="sm" variant="outline" data-testid={`admin-unsuspend-${u.user_id}`} onClick={() => unsuspend(u)} className="rounded-sm">Reativar</Button>
                      ) : (
                        <Button size="sm" variant="ghost" data-testid={`admin-suspend-${u.user_id}`} onClick={() => { setTarget(u); setSuspendDialog(true); }} title="Suspender" className="text-destructive hover:bg-destructive/10"><Ban size={14}/></Button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {users.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-sm text-muted-foreground">Sem resultados</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <Dialog open={warnDialog} onOpenChange={setWarnDialog}>
        <DialogContent className="rounded-sm">
          <DialogHeader><DialogTitle>Avisar {target?.name}</DialogTitle></DialogHeader>
          <Textarea data-testid="admin-warn-message" rows={4} placeholder="Motivo do aviso..." value={warn.message} onChange={(e) => setWarn({ message: e.target.value })} className="rounded-sm" />
          <DialogFooter><Button data-testid="admin-warn-submit" onClick={submitWarn} className="rounded-sm">Enviar aviso</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={suspendDialog} onOpenChange={setSuspendDialog}>
        <DialogContent className="rounded-sm">
          <DialogHeader><DialogTitle>Suspender {target?.name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="font-mono uppercase text-[11px] tracking-wider">Dias</Label>
              <Input data-testid="admin-suspend-days" type="number" min={1} max={365} value={susp.days} onChange={(e) => setSusp({ ...susp, days: e.target.value })} className="rounded-sm" />
            </div>
            <div>
              <Label className="font-mono uppercase text-[11px] tracking-wider">Motivo (opcional)</Label>
              <Textarea data-testid="admin-suspend-reason" rows={3} value={susp.reason} onChange={(e) => setSusp({ ...susp, reason: e.target.value })} className="rounded-sm" />
            </div>
          </div>
          <DialogFooter><Button data-testid="admin-suspend-submit" onClick={submitSuspend} className="rounded-sm bg-destructive hover:bg-destructive/80">Suspender</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
