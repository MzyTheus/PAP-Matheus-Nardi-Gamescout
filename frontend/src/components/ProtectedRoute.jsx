import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth-context";

export default function ProtectedRoute({ children, requireVerified = true }) {
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
  // Force email verification before accessing protected pages (except verify page itself)
  if (requireVerified && user.needs_verification && !location.pathname.startsWith("/verificar-email")) {
    return <Navigate to="/verificar-email" replace />;
  }
  return children;
}
