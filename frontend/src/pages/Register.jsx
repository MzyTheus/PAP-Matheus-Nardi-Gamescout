import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import { Gamepad2, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function Register() {
  const { user, register } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { if (user) nav(user.needs_verification ? "/verificar-email" : "/", { replace: true }); }, [user, nav]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const u = await register(name, email, password);
      toast.success("Conta criada — verifica o teu email");
      nav(u?.needs_verification === false ? "/" : "/verificar-email");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center p-8">
      <div className="w-full max-w-md space-y-8">
        <Link to="/" className="flex items-center gap-2 justify-center">
          <span className="grid place-items-center w-10 h-10 bg-primary text-primary-foreground rounded-sm">
            <Gamepad2 size={20} strokeWidth={2.5} />
          </span>
          <span className="font-heading font-black text-xl uppercase tracking-tight">Game<span className="text-primary">Scout</span></span>
        </Link>
        <div className="text-center">
          <div className="gs-overline mb-2">Criar conta</div>
          <h2 className="font-heading font-black text-3xl uppercase tracking-tight">Entra na comunidade</h2>
          <p className="text-sm text-muted-foreground mt-2">Já tens conta? <Link to="/login" className="text-primary underline-offset-4 hover:underline">Inicia sessão</Link></p>
        </div>

        <form onSubmit={onSubmit} data-testid="register-form" className="space-y-4 gs-card p-6">
          <div className="space-y-1.5">
            <Label className="font-mono uppercase text-[11px] tracking-wider">Nome de utilizador</Label>
            <Input data-testid="register-name" required minLength={2} value={name} onChange={(e) => setName(e.target.value)} className="h-11 rounded-sm" />
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono uppercase text-[11px] tracking-wider">Email Gmail</Label>
            <Input data-testid="register-email" type="email" placeholder="exemplo@gmail.com" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-11 rounded-sm" />
            <div className="font-mono text-[10px] text-muted-foreground tracking-wider">Apenas contas @gmail.com — receberás um código de verificação por email</div>
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono uppercase text-[11px] tracking-wider">Password (mín. 6)</Label>
            <Input data-testid="register-password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 rounded-sm" />
          </div>
          <Button type="submit" disabled={submitting} data-testid="register-submit" className="w-full h-11 rounded-sm font-mono uppercase tracking-wider">
            {submitting ? "A criar…" : <>Criar conta <ArrowRight size={16} className="ml-2" /></>}
          </Button>
        </form>
      </div>
    </div>
  );
}
