import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, formatApiError } from "./api";

const AuthCtx = createContext({
  user: undefined,
  loading: true,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/users/me/full");
      setUser(data);
      return data;
    } catch (e) {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Skip /me check if returning from OAuth callback so AuthCallback exchanges first
    if (typeof window !== "undefined" && window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    refresh();
  }, [refresh]);

  const login = async (email, password) => {
    try {
      await api.post("/auth/login", { email, password });
      await refresh();
    } catch (e) {
      throw new Error(formatApiError(e.response?.data?.detail, "Falha no login"));
    }
  };

  const register = async (name, email, password) => {
    try {
      await api.post("/auth/register", { name, email, password });
      await refresh();
    } catch (e) {
      throw new Error(formatApiError(e.response?.data?.detail, "Falha no registo"));
    }
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
