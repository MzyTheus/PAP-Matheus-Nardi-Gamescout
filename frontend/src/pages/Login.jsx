import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import { Gamepad2, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { if (user) nav(user.needs_verification ? "/verificar-email" : "/", { replace: true }); }, [user, nav]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const u = await login(email, password);
      toast.success("Bem-vindo ao GameScout");
      nav(u?.needs_verification ? "/verificar-email" : "/");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const onGoogle = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:block relative gs-grid-bg overflow-hidden">
        <img
          src="https://images.unsplash.com/photo-1744391309979-3325fcc3079a?crop=entropy&cs=srgb&fm=jpg&w=1200&q=80"
          alt="" aria-hidden
          className="absolute inset-0 w-full h-full object-cover opacity-40 mix-blend-screen"
        />
        <div className="absolute inset-0 bg-gradient-to-tr from-background via-background/60 to-transparent" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12">
          <Link to="/" className="flex items-center gap-2">
            <span className="grid place-items-center w-10 h-10 bg-primary text-primary-foreground rounded-sm">
              <Gamepad2 size={20} strokeWidth={2.5} />
            </span>
            <span className="font-heading font-black text-xl uppercase tracking-tight">Game<span className="text-primary">Scout</span></span>
          </Link>
          <div className="space-y-6 max-w-md">
            <div className="gs-overline">A tua próxima obsessão</div>
            <h1 className="font-heading font-black text-5xl uppercase leading-[0.95] tracking-tighter">
              Avalia. <span className="text-primary">Descobre.</span> Joga junto.
            </h1>
            <p className="text-muted-foreground leading-relaxed">
              Junta-te a uma comunidade de jogadores que partilham avaliações honestas, guias afiados e procuram parceiros para a próxima missão.
            </p>
            <div className="flex flex-wrap gap-2 font-mono text-[11px] uppercase tracking-wider">
              <span className="px-3 py-1 border border-border rounded-sm">Avaliações detalhadas</span>
              <span className="px-3 py-1 border border-border rounded-sm">Guias de elite</span>
              <span className="px-3 py-1 border border-border rounded-sm">Pedidos de ajuda</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8 lg:p-12">
        <div className="w-full max-w-md space-y-8">
          <div className="lg:hidden flex items-center gap-2 mb-4">
            <span className="grid place-items-center w-10 h-10 bg-primary text-primary-foreground rounded-sm">
              <Gamepad2 size={20} strokeWidth={2.5} />
            </span>
            <span className="font-heading font-black text-xl uppercase tracking-tight">Game<span className="text-primary">Scout</span></span>
          </div>
          <div>
            <div className="gs-overline mb-2">Início de sessão</div>
            <h2 className="font-heading font-black text-3xl uppercase tracking-tight">Entra na tua conta</h2>
            <p className="text-sm text-muted-foreground mt-2">Ou <Link to="/registo" className="text-primary underline-offset-4 hover:underline">cria uma conta nova</Link></p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="font-mono uppercase text-[11px] tracking-wider">Email Gmail</Label>
              <Input id="email" data-testid="login-email" type="email" placeholder="exemplo@gmail.com" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-11 rounded-sm" />
              <div className="font-mono text-[10px] text-muted-foreground tracking-wider">Apenas contas @gmail.com são aceites</div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password" className="font-mono uppercase text-[11px] tracking-wider">Password</Label>
              <Input id="password" data-testid="login-password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 rounded-sm" />
            </div>
            <Button type="submit" disabled={submitting} data-testid="login-submit" className="w-full h-11 rounded-sm font-mono uppercase tracking-wider">
              {submitting ? "A entrar…" : <>Entrar <ArrowRight size={16} className="ml-2" /></>}
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
            <div className="relative flex justify-center"><span className="bg-background px-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">ou</span></div>
          </div>

          <Button type="button" variant="outline" data-testid="login-google" onClick={onGoogle} className="w-full h-11 rounded-sm font-mono uppercase tracking-wider">
            <svg width="16" height="16" viewBox="0 0 24 24" className="mr-2"><path fill="#FFC107" d="M21.8 10.05H12v3.9h5.6c-.5 2.4-2.5 3.9-5.6 3.9-3.4 0-6.2-2.7-6.2-6.1s2.8-6.1 6.2-6.1c1.6 0 3 .6 4 1.5l2.7-2.7C16.6 2.7 14.5 2 12 2 6.5 2 2 6.5 2 12s4.5 10 10 10c5.8 0 9.6-4.1 9.6-9.8 0-.7-.1-1.4-.3-2.05z"/></svg>
            Continuar com Google
          </Button>
        </div>
      </div>
    </div>
  );
}
