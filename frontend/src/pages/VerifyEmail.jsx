import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail, RefreshCw, Check } from "lucide-react";
import { toast } from "sonner";

export default function VerifyEmail() {
  const { user, refresh, logout } = useAuth();
  const nav = useNavigate();
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (user === null) { nav("/login"); return; }
    if (user && user.needs_verification === false) { nav("/"); }
  }, [user, nav]);

  // Cooldown timer for resend
  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  const submit = async (e) => {
    e.preventDefault();
    if (code.trim().length !== 6) { toast.error("Código deve ter 6 dígitos"); return; }
    setSubmitting(true);
    try {
      await api.post("/auth/verify-email", { code: code.trim() });
      toast.success("Email confirmado! 🎉");
      await refresh();
      nav("/");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Código inválido");
    } finally { setSubmitting(false); }
  };

  const resend = async () => {
    if (cooldown > 0) return;
    setResending(true);
    try {
      await api.post("/auth/resend-code");
      toast.success("Código reenviado para o teu email");
      setCooldown(45);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro");
    } finally { setResending(false); }
  };

  if (!user) return null;

  return (
    <div className="max-w-md mx-auto pt-10 space-y-8">
      <div className="text-center">
        <div className="inline-grid place-items-center w-14 h-14 bg-primary/10 border border-primary/40 rounded-sm mb-4">
          <Mail size={26} className="text-primary" />
        </div>
        <div className="gs-overline mb-2">Verificação de email</div>
        <h1 className="font-heading font-black text-3xl uppercase tracking-tight">Confirma o teu email</h1>
        <p className="text-sm text-muted-foreground mt-3">
          Enviámos um código de 6 dígitos para <b className="text-foreground">{user.email}</b>. Verifica também a pasta de spam.
        </p>
      </div>

      <form onSubmit={submit} className="gs-card p-6 space-y-4" data-testid="verify-form">
        <div className="space-y-1.5">
          <Label className="font-mono uppercase text-[11px] tracking-wider">Código de 6 dígitos</Label>
          <Input
            data-testid="verify-code"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="123456"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            className="h-14 rounded-sm font-mono text-2xl text-center tracking-[0.4em]"
          />
        </div>
        <Button type="submit" disabled={submitting || code.length !== 6} data-testid="verify-submit" className="w-full h-11 rounded-sm font-mono uppercase tracking-wider">
          {submitting ? "A confirmar…" : <><Check size={16} className="mr-2"/> Confirmar email</>}
        </Button>
      </form>

      <div className="text-center space-y-3">
        <Button variant="outline" size="sm" data-testid="verify-resend" onClick={resend} disabled={resending || cooldown > 0} className="rounded-sm font-mono uppercase tracking-wider text-xs">
          <RefreshCw size={14} className={`mr-2 ${resending ? "animate-spin" : ""}`} />
          {cooldown > 0 ? `Reenviar em ${cooldown}s` : "Reenviar código"}
        </Button>
        <div className="font-mono text-[10px] text-muted-foreground tracking-wider">
          Email errado?{" "}
          <button data-testid="verify-logout" onClick={async () => { await logout(); nav("/registo"); }} className="text-primary hover:underline">Cria nova conta</button>
        </div>
      </div>
    </div>
  );
}
