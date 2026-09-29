import { Outlet } from "react-router";
import { NotFoundPage } from "@/app/NotFoundPage";
import { useMe } from "./useMe";

/** Onglet Admin : un non-admin voit une page introuvable (on ne révèle pas son existence). */
export function RequireAdmin() {
  const { me, isPending } = useMe();
  if (isPending) return null;
  return me?.role === "admin" ? <Outlet /> : <NotFoundPage />;
}
