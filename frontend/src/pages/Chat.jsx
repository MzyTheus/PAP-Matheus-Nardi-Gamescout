import { useEffect, useRef, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cacheBust } from "@/lib/format";
import { MessageSquare, Send, ArrowLeft, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function Chat() {
  const { friendId } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const [threads, setThreads] = useState([]);
  const [messages, setMessages] = useState([]);
  const [friend, setFriend] = useState(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);
  const lastTsRef = useRef(null);

  // Load thread list
  useEffect(() => {
    if (!user) return;
    api.get("/chat/threads").then((r) => setThreads(r.data || []));
  }, [user, friendId]);

  // Load friend info + messages when a friendId is selected
  useEffect(() => {
    if (!friendId) { setMessages([]); setFriend(null); lastTsRef.current = null; return; }
    api.get(`/users/${friendId}`).then((r) => setFriend(r.data)).catch(() => setFriend(null));
    api.get(`/chat/dm/${friendId}`).then((r) => {
      setMessages(r.data || []);
      if (r.data?.length) lastTsRef.current = r.data[r.data.length - 1].created_at;
    }).catch((e) => {
      toast.error(e.response?.data?.detail || "Não foi possível abrir a conversa");
    });
  }, [friendId]);

  // Poll for new messages every 4s
  useEffect(() => {
    if (!friendId) return;
    const id = setInterval(async () => {
      try {
        const params = lastTsRef.current ? { after: lastTsRef.current } : {};
        const { data } = await api.get(`/chat/dm/${friendId}`, { params });
        if (data?.length) {
          setMessages((prev) => [...prev, ...data]);
          lastTsRef.current = data[data.length - 1].created_at;
        }
      } catch (_) {/* silent */}
    }, 4000);
    return () => clearInterval(id);
  }, [friendId]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const sendMessage = async (e) => {
    e.preventDefault();
    const txt = draft.trim();
    if (!txt || !friendId) return;
    setSending(true);
    try {
      const { data } = await api.post(`/chat/dm/${friendId}`, { content: txt });
      setMessages((prev) => [...prev, data]);
      lastTsRef.current = data.created_at;
      setDraft("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao enviar");
    } finally {
      setSending(false);
    }
  };

  const deleteMessage = async (msgId) => {
    try {
      await api.delete(`/chat/messages/${msgId}`);
      setMessages((prev) => prev.filter((m) => m.msg_id !== msgId));
      toast.success("Mensagem apagada");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro");
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <div className="gs-overline flex items-center gap-1.5"><MessageSquare size={12}/> Conversas</div>
        <h1 className="font-heading font-black text-3xl sm:text-5xl uppercase tracking-tighter mt-1">Chat</h1>
        <p className="text-sm text-muted-foreground mt-2">Mensagens privadas com os teus amigos.</p>
      </header>

      <div className="grid md:grid-cols-[280px_1fr] gap-4 min-h-[60vh]">
        {/* Sidebar — thread list */}
        <aside className={`gs-card overflow-hidden ${friendId ? "hidden md:block" : ""}`} data-testid="chat-threads">
          <div className="px-4 py-3 border-b border-border font-mono text-xs uppercase tracking-widest text-muted-foreground">Amigos</div>
          {threads.length === 0 ? (
            <div className="p-6 text-sm text-muted-foreground">
              Sem amigos ainda. <Link to="/amigos" className="text-primary hover:underline">Encontra pessoas</Link> para começar a conversar.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {threads.map((t) => (
                <li key={t.user_id}>
                  <button
                    data-testid={`chat-thread-${t.user_id}`}
                    onClick={() => nav(`/chat/${t.user_id}`)}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted ${friendId === t.user_id ? "bg-muted" : ""}`}>
                    <Avatar className="h-9 w-9 rounded-sm">
                      <AvatarImage src={t.picture ? cacheBust(t.picture, (t.picture || "").length) : null} />
                      <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-xs">{(t.name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium truncate">{t.name}</div>
                      <div className="text-xs text-muted-foreground truncate">
                        {t.last_message ? (t.last_sender === user?.user_id ? "Tu: " : "") + t.last_message : "Iniciar conversa"}
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Main — message area */}
        <section className={`gs-card flex flex-col ${friendId ? "" : "hidden md:flex md:items-center md:justify-center"}`} data-testid="chat-window">
          {!friendId ? (
            <div className="text-center text-sm text-muted-foreground p-8">
              <MessageSquare size={32} className="mx-auto mb-3 opacity-40" />
              Seleciona um amigo para começar a conversar.
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-border flex items-center gap-3">
                <button onClick={() => nav("/chat")} className="md:hidden text-muted-foreground hover:text-primary"><ArrowLeft size={16}/></button>
                {friend && (
                  <Link to={`/perfil/${friend.user_id}`} className="flex items-center gap-3 group/u">
                    <Avatar className="h-9 w-9 rounded-sm">
                      <AvatarImage src={friend.picture ? cacheBust(friend.picture, (friend.picture || "").length) : null} />
                      <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-xs">{(friend.name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div>
                      <div className="text-sm font-semibold group-hover/u:text-primary">{friend.name}</div>
                      <div className="font-mono text-[10px] text-muted-foreground tracking-wider uppercase">@{friend.user_id?.replace(/^user_/, "")}</div>
                    </div>
                  </Link>
                )}
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2 max-h-[55vh]">
                {messages.length === 0 ? (
                  <div className="text-center text-xs font-mono uppercase tracking-wider text-muted-foreground py-12">Sem mensagens. Envia a primeira!</div>
                ) : messages.map((m) => {
                  const mine = m.sender_id === user?.user_id;
                  const canDelete = mine || user?.role === "admin";
                  return (
                    <div key={m.msg_id} data-testid={`chat-msg-${m.msg_id}`} className={`flex group/msg ${mine ? "justify-end" : "justify-start"}`}>
                      {canDelete && mine && (
                        <button
                          data-testid={`chat-msg-delete-${m.msg_id}`}
                          onClick={() => deleteMessage(m.msg_id)}
                          title="Apagar mensagem"
                          className="self-center mr-1 opacity-0 group-hover/msg:opacity-100 transition text-muted-foreground hover:text-destructive p-1 rounded-sm"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                      <div className={`max-w-[78%] px-3 py-2 text-sm rounded-sm ${mine ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"}`}>
                        <div className="whitespace-pre-line break-words">{m.content}</div>
                        <div className={`mt-1 font-mono text-[9px] tracking-wider ${mine ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                          {new Date(m.created_at).toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" })}
                        </div>
                      </div>
                      {canDelete && !mine && (
                        <button
                          data-testid={`chat-msg-delete-${m.msg_id}`}
                          onClick={() => deleteMessage(m.msg_id)}
                          title="Apagar mensagem (admin)"
                          className="self-center ml-1 opacity-0 group-hover/msg:opacity-100 transition text-muted-foreground hover:text-destructive p-1 rounded-sm"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  );
                })}
                <div ref={bottomRef} />
              </div>

              <form onSubmit={sendMessage} className="border-t border-border p-3 flex gap-2">
                <Input
                  data-testid="chat-input"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Escreve uma mensagem…"
                  className="rounded-sm"
                  maxLength={2000}
                />
                <Button data-testid="chat-send" type="submit" disabled={sending || !draft.trim()} className="rounded-sm">
                  <Send size={16} />
                </Button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
