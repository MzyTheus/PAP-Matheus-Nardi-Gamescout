import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function AuthCallback() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const fragment = window.location.hash || "";
    const params = new URLSearchParams(fragment.startsWith("#") ? fragment.slice(1) : fragment);
    const sessionId = params.get("session_id");

    (async () => {
      if (!sessionId) {
        nav("/login", { replace: true });
        return;
      }
      try {
        await api.post("/auth/google/session", { session_id: sessionId });
        await refresh();
        // Clean URL hash and redirect home
        window.history.replaceState({}, "", "/");
        nav("/", { replace: true });
      } catch (e) {
        nav("/login?error=oauth", { replace: true });
      }
    })();
  }, [nav, refresh]);

  return (
    <div className="min-h-screen grid place-items-center">
      <div className="text-center space-y-3">
        <div className="font-heading font-black text-2xl uppercase tracking-tight text-primary">A iniciar sessão…</div>
        <div className="font-mono text-xs text-muted-foreground tracking-wider">A validar com Google</div>
      </div>
    </div>
  );
}
