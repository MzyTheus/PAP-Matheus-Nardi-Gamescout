import { useEffect, useRef, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cacheBust } from "@/lib/format";
import { ArrowLeft, Send, Users, LogOut, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function CommunityDetail() {
  const { communityId } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const [community, setCommunity] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const lastTsRef = useRef(null);
  const bottomRef = useRef(null);

  const loadCommunity = async () => {
    try {
      const { data } = await api.get(`/communities/${communityId}`);
      setCommunity(data);
      return data;
    } catch (e) {
      toast.error("Comunidade não encontrada");
      nav("/comunidades");
    }
  };

  const loadMessages = async () => {
    try {
      const { data } = await api.get(`/communities/${communityId}/messages`);
      setMessages(data || []);
      if (data?.length) lastTsRef.current = data[data.length - 1].created_at;
    } catch (e) {
      // 403 if not member — handled by UI
    }
  };

  useEffect(() => {
    (async () => {
      const c = await loadCommunity();
      if (c?.is_member) await loadMessages();
    })();
    // eslint-disable-next-line
  }, [communityId]);

  // Poll
  useEffect(() => {
    if (!community?.is_member) return;
    const id = setInterval(async () => {
      try {
        const params = lastTsRef.current ? { after: lastTsRef.current } : {};
        const { data } = await api.get(`/communities/${communityId}/messages`, { params });
        if (data?.length) {
          setMessages((prev) => [...prev, ...data]);
          lastTsRef.current = data[data.length - 1].created_at;
        }
      } catch (_) {/* silent */}
    }, 4000);
    return () => clearInterval(id);
  }, [community?.is_member, communityId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length]);

  const send = async (e) => {
    e.preventDefault();
    const txt = draft.trim();
    if (!txt) return;
    setSending(true);
    try {
      const { data } = await api.post(`/communities/${communityId}/messages`, { content: txt });
      setMessages((p) => [...p, data]);
      lastTsRef.current = data.created_at;
      setDraft("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro");
    } finally { setSending(false); }
  };

  const join = async () => {
    if (!user) { nav("/login"); return; }
    try {
      await api.post(`/communities/${communityId}/join`);
      const c = await loadCommunity();
      if (c?.is_member) await loadMessages();
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  const leave = async () => {
    try {
      await api.delete(`/communities/${communityId}/leave`);
      toast.success("Saíste da comunidade");
      nav("/comunidades");
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  const deleteMsg = async (msgId) => {
    try {
      await api.delete(`/communities/${communityId}/messages/${msgId}`);
      setMessages((p) => p.filter((m) => m.msg_id !== msgId));
      toast.success("Mensagem apagada");
    } catch (e) { toast.error(e.response?.data?.detail || "Erro"); }
  };

  if (!community) return null;

  return (
    <div className="space-y-6">
      <Link to="/comunidades" className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:text-primary"><ArrowLeft size={14}/> Todas as comunidades</Link>

      <header className="gs-card p-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="gs-overline flex items-center gap-1.5"><Users size={12}/> Comunidade</div>
          <h1 className="font-heading font-black text-2xl sm:text-3xl uppercase tracking-tighter mt-1">{community.name}</h1>
          {community.description && <p className="text-sm text-muted-foreground mt-2 max-w-2xl">{community.description}</p>}
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground mt-2">{community.members_count} {community.members_count === 1 ? "membro" : "membros"}</div>
        </div>
        {community.is_member ? (
          <Button variant="outline" size="sm" onClick={leave} data-testid="community-leave" className="rounded-sm font-mono uppercase tracking-wider"><LogOut size={14} className="mr-1"/> Sair</Button>
        ) : (
          <Button size="sm" onClick={join} data-testid="community-join-detail" className="rounded-sm font-mono uppercase tracking-wider">Juntar-me</Button>
        )}
      </header>

      {!community.is_member ? (
        <div className="gs-card p-8 text-center text-sm text-muted-foreground">Junta-te à comunidade para ver e enviar mensagens.</div>
      ) : (
        <section className="gs-card flex flex-col" data-testid="community-chat">
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 max-h-[60vh] min-h-[300px]">
            {messages.length === 0 ? (
              <div className="text-center text-xs font-mono uppercase tracking-wider text-muted-foreground py-12">Sem mensagens. Sê o primeiro!</div>
            ) : messages.map((m) => {
              const mine = m.sender_id === user?.user_id;
              const isOwner = community.owner_id === user?.user_id;
              const canDelete = mine || isOwner || user?.role === "admin";
              return (
                <div key={m.msg_id} data-testid={`community-msg-${m.msg_id}`} className={`flex gap-2 group/cmsg ${mine ? "justify-end" : "justify-start"}`}>
                  {!mine && (
                    <Link to={`/perfil/${m.sender_id}`} className="shrink-0">
                      <Avatar className="h-7 w-7 rounded-sm">
                        <AvatarImage src={m.sender_picture ? cacheBust(m.sender_picture, (m.sender_picture || "").length) : null} />
                        <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-[10px]">{(m.sender_name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                      </Avatar>
                    </Link>
                  )}
                  <div className={`max-w-[75%] ${mine ? "items-end" : "items-start"} flex flex-col`}>
                    {!mine && <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">{m.sender_name}</div>}
                    <div className={`relative px-3 py-2 text-sm rounded-sm ${mine ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"}`}>
                      <div className="whitespace-pre-line break-words">{m.content}</div>
                      <div className={`mt-1 font-mono text-[9px] tracking-wider ${mine ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                        {new Date(m.created_at).toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" })}
                      </div>
                    </div>
                  </div>
                  {canDelete && (
                    <button
                      data-testid={`community-msg-delete-${m.msg_id}`}
                      onClick={() => deleteMsg(m.msg_id)}
                      title={mine ? "Apagar mensagem" : "Apagar (moderação)"}
                      className="self-center opacity-0 group-hover/cmsg:opacity-100 transition text-muted-foreground hover:text-destructive p-1 rounded-sm"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>
          <form onSubmit={send} className="border-t border-border p-3 flex gap-2">
            <Input data-testid="community-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Escreve para a comunidade…" maxLength={2000} className="rounded-sm" />
            <Button data-testid="community-send" type="submit" disabled={sending || !draft.trim()} className="rounded-sm"><Send size={16}/></Button>
          </form>
        </section>
      )}
    </div>
  );
}
