import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth-context";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="font-mono text-sm text-muted-foreground tracking-wider">A CARREGAR…</div>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}
