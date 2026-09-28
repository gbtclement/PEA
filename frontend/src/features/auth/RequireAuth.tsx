import { Navigate, Outlet, useLocation } from "react-router";
import { loginPath } from "./redirect";
import { useMe } from "./useMe";

/** Pages privées : visiteur renvoyé vers la connexion, puis ramené ici. */
export function RequireAuth() {
  const { me, isPending } = useMe();
  const location = useLocation();
  if (isPending) return null;
  if (!me) return <Navigate to={loginPath(location)} replace />;
  return <Outlet />;
}
