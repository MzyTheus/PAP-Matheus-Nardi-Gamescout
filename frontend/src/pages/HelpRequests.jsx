import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, MessageCircleQuestion, Users, Lightbulb, Send, MoreVertical, Edit2, Trash2, Save, X } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

const KIND_LABEL = {
  "ajuda": { label: "Pedido de ajuda", icon: MessageCircleQuestion },
  "jogar-junto": { label: "Procura companhia", icon: Users },
  "dica": { label: "Pede dica", icon: Lightbulb },
};

function HelpItem({ item, onReply, onChanged, currentUser }) {
  const [reply, setReply] = useState("");
  const [editing, setEditing] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [editForm, setEditForm] = useState({ title: item.title, content: item.content, kind: item.kind });
  const [editingReplyId, setEditingReplyId] = useState(null);
  const [replyDraft, setReplyDraft] = useState("");
  const meta = KIND_LABEL[item.kind] || KIND_LABEL.ajuda;
  const Ico = meta.icon;
  const isOwner = currentUser && (currentUser.user_id === item.author_id || currentUser.role === "admin");

  const saveEdit = async () => {
    try {
      await api.patch(`/help-requests/${item.help_id}`, editForm);
      toast.success("Atualizado");
      setEditing(false);
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  const removeItem = async () => {
    try { await api.delete(`/help-requests/${item.help_id}`); toast.success("Pedido removido"); onChanged && onChanged(); }
    catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  const saveReplyEdit = async (rid) => {
    try {
      await api.patch(`/help-requests/${item.help_id}/replies/${rid}`, { content: replyDraft });
      toast.success("Resposta atualizada");
      setEditingReplyId(null);
      onChanged && onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  const removeReply = async (rid) => {
    try { await api.delete(`/help-requests/${item.help_id}/replies/${rid}`); toast.success("Resposta removida"); onChanged && onChanged(); }
    catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  return (
    <article data-testid={`help-${item.help_id}`} className="gs-card p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <Avatar className="h-9 w-9 rounded-sm">
            <AvatarImage src={item.author_picture} />
            <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-xs">{(item.author_name || "U").slice(0, 2).toUpperCase()}</AvatarFallback>
          </Avatar>
          <div>
            <div className="font-semibold text-sm"><Link to={`/perfil/${item.author_id}`} className="hover:text-primary">{item.author_name}</Link></div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-primary">{meta.label}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Ico size={20} className="text-primary/60" />
          {isOwner && !editing && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid={`help-menu-${item.help_id}`} className="p-1 rounded-sm hover:bg-muted text-muted-foreground"><MoreVertical size={16}/></button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="rounded-sm">
                <DropdownMenuItem data-testid={`help-edit-${item.help_id}`} onClick={() => setEditing(true)}><Edit2 size={14} className="mr-2"/> Editar</DropdownMenuItem>
                <DropdownMenuItem data-testid={`help-delete-${item.help_id}`} className="text-destructive focus:text-destructive" onClick={() => setConfirmOpen(true)}><Trash2 size={14} className="mr-2"/> Apagar</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>

      {editing ? (
        <div className="space-y-2">
          <Input value={editForm.title} onChange={(e) => setEditForm({ ...editForm, title: e.target.value })} className="rounded-sm font-heading" />
          <Textarea rows={4} value={editForm.content} onChange={(e) => setEditForm({ ...editForm, content: e.target.value })} className="rounded-sm" />
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditing(false)} className="rounded-sm">Cancelar</Button>
            <Button size="sm" data-testid={`help-save-${item.help_id}`} onClick={saveEdit} className="rounded-sm"><Save size={14} className="mr-1"/> Guardar</Button>
          </div>
        </div>
      ) : (
        <>
          <h3 className="font-heading font-bold text-lg tracking-tight">{item.title}</h3>
          <p className="text-sm text-foreground/90 whitespace-pre-line">{item.content}</p>
        </>
      )}

      {(item.replies?.length || 0) > 0 && (
        <div className="border-t border-border pt-3 space-y-2">
          {item.replies.map((r) => {
            const replyOwner = currentUser && (currentUser.user_id === r.author_id || currentUser.role === "admin");
            const isEditing = editingReplyId === r.reply_id;
            return (
              <div key={r.reply_id} data-testid={`reply-${r.reply_id}`} className="flex gap-2 items-start group">
                <Avatar className="h-6 w-6 rounded-sm">
                  <AvatarImage src={r.author_picture} />
                  <AvatarFallback className="rounded-sm bg-muted font-mono text-[10px]">{(r.author_name || "U").slice(0, 2).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="text-sm flex-1 min-w-0">
                  <div><span className="font-semibold mr-2">{r.author_name}</span></div>
                  {isEditing ? (
                    <div className="flex gap-2 mt-1">
                      <Input value={replyDraft} onChange={(e) => setReplyDraft(e.target.value)} className="rounded-sm" />
                      <Button size="sm" data-testid={`reply-save-${r.reply_id}`} onClick={() => saveReplyEdit(r.reply_id)} className="rounded-sm"><Save size={12}/></Button>
                      <Button size="sm" variant="outline" onClick={() => setEditingReplyId(null)} className="rounded-sm"><X size={12}/></Button>
                    </div>
                  ) : (
                    <span className="text-foreground/90 break-words">{r.content}</span>
                  )}
                </div>
                {replyOwner && !isEditing && (
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                    <button data-testid={`reply-edit-${r.reply_id}`} onClick={() => { setEditingReplyId(r.reply_id); setReplyDraft(r.content); }} className="p-1 text-muted-foreground hover:text-primary"><Edit2 size={12}/></button>
                    <button data-testid={`reply-delete-${r.reply_id}`} onClick={() => removeReply(r.reply_id)} className="p-1 text-muted-foreground hover:text-destructive"><Trash2 size={12}/></button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {currentUser && (
        <div className="flex gap-2 pt-2 border-t border-border">
          <Input
            data-testid={`reply-input-${item.help_id}`}
            placeholder="Responder…" value={reply} onChange={(e) => setReply(e.target.value)} className="rounded-sm"
          />
          <Button
            data-testid={`reply-btn-${item.help_id}`}
            disabled={reply.trim().length < 2}
            onClick={async () => { await onReply(item.help_id, reply); setReply(""); }}
            className="rounded-sm"
          ><Send size={14} /></Button>
        </div>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent className="rounded-sm">
          <AlertDialogHeader><AlertDialogTitle>Apagar pedido?</AlertDialogTitle><AlertDialogDescription>Esta ação não pode ser revertida.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-sm">Cancelar</AlertDialogCancel>
            <AlertDialogAction data-testid={`help-delete-confirm-${item.help_id}`} className="rounded-sm" onClick={removeItem}>Apagar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </article>
  );
}

export default function HelpRequests() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", content: "", kind: "ajuda" });
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    const sp = filter === "all" ? {} : { kind: filter };
    api.get("/help-requests", { params: sp }).then((r) => setItems(r.data));
  };
  useEffect(load, [filter]);

  const create = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/help-requests", form);
      toast.success("Publicado!");
      setForm({ title: "", content: "", kind: "ajuda" });
      setOpen(false);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro");
    } finally {
      setSubmitting(false);
    }
  };

  const reply = async (helpId, content) => {
    try {
      await api.post(`/help-requests/${helpId}/replies`, { content });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="gs-overline">Comunidade</div>
          <h1 className="font-heading font-black text-3xl sm:text-4xl uppercase tracking-tight mt-1">Pedidos de Ajuda</h1>
          <p className="text-sm text-muted-foreground mt-2 max-w-xl">Pede dicas, procura pessoas para jogar, ou ajuda os outros — ganha respeito da comunidade.</p>
        </div>
        {user && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button data-testid="help-new-btn" className="rounded-sm font-mono uppercase tracking-wider"><Plus size={14} className="mr-2"/> Novo pedido</Button>
            </DialogTrigger>
            <DialogContent className="rounded-sm max-w-lg">
              <DialogHeader><DialogTitle className="font-heading uppercase tracking-tight">Novo pedido</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="font-mono uppercase text-[11px] tracking-wider">Tipo</Label>
                  <Select value={form.kind} onValueChange={(v) => setForm({ ...form, kind: v })}>
                    <SelectTrigger data-testid="help-kind" className="rounded-sm"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ajuda">Pedido de ajuda</SelectItem>
                      <SelectItem value="jogar-junto">Procurar companhia</SelectItem>
                      <SelectItem value="dica">Pedir dica</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="font-mono uppercase text-[11px] tracking-wider">Título</Label>
                  <Input data-testid="help-title" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="rounded-sm" />
                </div>
                <div className="space-y-1.5">
                  <Label className="font-mono uppercase text-[11px] tracking-wider">Descrição</Label>
                  <Textarea data-testid="help-content" required rows={5} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} className="rounded-sm" />
                </div>
                <div className="flex justify-end"><Button type="submit" disabled={submitting} data-testid="help-submit" className="rounded-sm font-mono uppercase tracking-wider">{submitting ? "A publicar…" : "Publicar"}</Button></div>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {[["all", "Todos"], ["ajuda", "Ajuda"], ["jogar-junto", "Jogar junto"], ["dica", "Dicas"]].map(([k, l]) => (
          <button key={k} onClick={() => setFilter(k)} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider border rounded-sm transition ${filter === k ? "bg-primary text-primary-foreground border-primary" : "border-border hover:border-primary"}`}>{l}</button>
        ))}
      </div>

      {items.length === 0 ? (
        <div className="gs-card p-12 text-center">
          <MessageCircleQuestion size={32} className="mx-auto text-primary mb-3" />
          <div className="font-heading text-xl uppercase tracking-tight">Sem pedidos por aqui</div>
          <div className="font-mono text-sm text-muted-foreground mt-2">Sê o primeiro a pedir ou oferecer ajuda.</div>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {items.map((it) => (<HelpItem key={it.help_id} item={it} onReply={reply} onChanged={load} currentUser={user} />))}
        </div>
      )}
    </div>
  );
}
