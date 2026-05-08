import { Link, NavLink, useNavigate } from "react-router-dom";
import { Search, Gamepad2, Users, MessageSquareWarning, LogOut, User as UserIcon, Sun, Moon, Menu, Heart } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../lib/auth-context";
import { useTheme } from "../lib/use-theme";
import { handleOf, cacheBust } from "../lib/format";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";

export default function Navbar() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const nav = useNavigate();
  const [q, setQ] = useState("");

  const submitSearch = (e) => {
    e.preventDefault();
    if (q.trim()) nav(`/jogos?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-6 lg:px-10 h-16 flex items-center gap-6">
        <Link to="/" data-testid="navbar-logo" className="flex items-center gap-2 group">
          <span className="grid place-items-center w-9 h-9 bg-primary text-primary-foreground rounded-sm">
            <Gamepad2 size={18} strokeWidth={2.5} />
          </span>
          <span className="font-heading font-black text-lg tracking-tight uppercase hidden sm:block">
            Game<span className="text-primary">Scout</span>
          </span>
        </Link>

        <form onSubmit={submitSearch} className="flex-1 max-w-xl relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            data-testid="navbar-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Procurar jogos..."
            className="pl-9 h-10 rounded-sm bg-muted/30 border-border focus:border-primary"
          />
        </form>

        <nav className="hidden md:flex items-center gap-1">
          <NavLink data-testid="nav-feed" to="/" end className={({ isActive }) => `px-3 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>Feed</NavLink>
          <NavLink data-testid="nav-jogos" to="/jogos" className={({ isActive }) => `px-3 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>Jogos</NavLink>
          <NavLink data-testid="nav-top" to="/top" className={({ isActive }) => `px-3 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>Top</NavLink>
          <NavLink data-testid="nav-descobrir" to="/descobrir" className={({ isActive }) => `px-3 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>Descobrir</NavLink>
          <NavLink data-testid="nav-ajuda" to="/ajuda" className={({ isActive }) => `px-3 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>Ajuda</NavLink>
          <NavLink data-testid="nav-amigos" to="/amigos" className={({ isActive }) => `px-3 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>Amigos</NavLink>
          <NavLink data-testid="nav-chat" to="/chat" className={({ isActive }) => `px-3 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>Chat</NavLink>
          <NavLink data-testid="nav-comunidades" to="/comunidades" className={({ isActive }) => `px-3 py-2 text-sm font-mono uppercase tracking-wider transition-colors ${isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>Comunidades</NavLink>
        </nav>

        <Button data-testid="theme-toggle" variant="ghost" size="icon" onClick={toggle} className="rounded-sm">
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </Button>

        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid="user-menu" className="flex items-center gap-2 px-2 py-1 rounded-sm hover:bg-muted transition-colors">
                <Avatar className="h-8 w-8 rounded-sm">
                  <AvatarImage src={user.picture ? cacheBust(user.picture, (user.picture || "").length) : null} />
                  <AvatarFallback className="rounded-sm bg-primary text-primary-foreground font-mono text-xs">{(user.name || "U").slice(0,2).toUpperCase()}</AvatarFallback>
                </Avatar>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 rounded-sm">
              <div className="px-2 py-2">
                <div className="text-sm font-semibold truncate">{user.name}</div>
                <div className="text-xs text-muted-foreground font-mono truncate">{handleOf(user.user_id)}</div>
                <div className="text-xs text-muted-foreground font-mono mt-0.5">{user.points} pts · {user.rank?.name || "Novato"}</div>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem data-testid="menu-profile" onClick={() => nav(`/perfil/${user.user_id}`)}>
                <UserIcon size={14} className="mr-2" /> Meu Perfil
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="menu-wishlist" onClick={() => nav("/wishlist")}>
                <Heart size={14} className="mr-2" /> Wishlist
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="menu-edit" onClick={() => nav("/perfil/editar")}>
                Editar perfil
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem data-testid="menu-logout" onClick={async () => { await logout(); nav("/login"); }}>
                <LogOut size={14} className="mr-2" /> Terminar sessão
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Button data-testid="navbar-login" onClick={() => nav("/login")} className="rounded-sm font-mono uppercase tracking-wider text-xs">Entrar</Button>
        )}
      </div>
    </header>
  );
}
