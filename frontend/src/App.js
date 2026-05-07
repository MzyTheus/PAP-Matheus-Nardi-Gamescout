import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef } from "react";
import "@/App.css";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/use-theme";
import { Toaster } from "@/components/ui/sonner";
import Navbar from "@/components/Navbar";
import ProtectedRoute from "@/components/ProtectedRoute";

import Login from "@/pages/Login";
import Register from "@/pages/Register";
import AuthCallback from "@/pages/AuthCallback";
import Home from "@/pages/Home";
import GamesCatalog from "@/pages/GamesCatalog";
import GameDetail from "@/pages/GameDetail";
import Profile from "@/pages/Profile";
import EditProfile from "@/pages/EditProfile";
import ReviewForm from "@/pages/ReviewForm";
import GuideForm from "@/pages/GuideForm";
import HelpRequests from "@/pages/HelpRequests";
import Friends from "@/pages/Friends";
import Discover from "@/pages/Discover";
import TopGames from "@/pages/TopGames";
import Wishlist from "@/pages/Wishlist";

function ShellLayout({ children }) {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="mx-auto max-w-7xl px-6 lg:px-10 py-8">{children}</main>
      <footer className="border-t border-border mt-20">
        <div className="mx-auto max-w-7xl px-6 lg:px-10 py-10 flex flex-col sm:flex-row items-start sm:items-center gap-4 justify-between">
          <div>
            <div className="font-heading font-black uppercase tracking-tight">
              Game<span className="text-primary">Scout</span>
            </div>
            <div className="font-mono text-xs text-muted-foreground mt-1 tracking-wider">
              Comunidade de jogadores · Avaliações reais · Guias de elite
            </div>
          </div>
          <div className="font-mono text-[11px] text-muted-foreground tracking-wider uppercase">
            © {new Date().getFullYear()} GameScout · Feito com laranja
          </div>
        </div>
      </footer>
    </div>
  );
}

function AppRouter() {
  const location = useLocation();
  // CRITICAL: Detect Emergent OAuth callback synchronously during render
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/registo" element={<Register />} />
      <Route
        path="*"
        element={
          <ShellLayout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/jogos" element={<GamesCatalog />} />
              <Route path="/top" element={<TopGames />} />
              <Route path="/jogos/:gameId" element={<GameDetail />} />
              <Route path="/descobrir" element={<ProtectedRoute><Discover /></ProtectedRoute>} />
              <Route path="/wishlist" element={<ProtectedRoute><Wishlist /></ProtectedRoute>} />
              <Route path="/wishlist/:userId" element={<Wishlist />} />
              <Route path="/jogos/:gameId/avaliar" element={<ProtectedRoute><ReviewForm /></ProtectedRoute>} />
              <Route path="/jogos/:gameId/guia/novo" element={<ProtectedRoute><GuideForm /></ProtectedRoute>} />
              <Route path="/perfil/editar" element={<ProtectedRoute><EditProfile /></ProtectedRoute>} />
              <Route path="/perfil/:userId" element={<Profile />} />
              <Route path="/ajuda" element={<HelpRequests />} />
              <Route path="/amigos" element={<ProtectedRoute><Friends /></ProtectedRoute>} />
              <Route path="*" element={<div className="text-center py-20"><div className="font-heading text-6xl font-black text-primary">404</div><div className="font-mono text-sm text-muted-foreground mt-4">Página não encontrada</div></div>} />
            </Routes>
          </ShellLayout>
        }
      />
    </Routes>
  );
}

function ThemeBoot() {
  // Apply saved theme on mount
  useTheme();
  return null;
}

export default function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <ThemeBoot />
          <AppRouter />
          <Toaster richColors position="top-right" />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}
