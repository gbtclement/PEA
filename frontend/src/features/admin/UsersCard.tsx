import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, apiSend, type AdminUser, type AdminUserList } from "@/lib/api/client";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { DeleteUserDialog } from "./DeleteUserDialog";
import { EditUserDialog } from "./EditUserDialog";

type Sort = "email" | "first_name" | "last_name" | "role" | "is_premium" | "verified" | "created_at" | "last_login_at";
const COLUMNS: { key: Sort; label: string }[] = [
  { key: "first_name", label: "Prénom" }, { key: "last_name", label: "Nom" }, { key: "email", label: "Mail" },
  { key: "role", label: "Rôle" }, { key: "is_premium", label: "Premium" }, { key: "verified", label: "Validé" },
  { key: "created_at", label: "Inscription" }, { key: "last_login_at", label: "Dernière connexion" },
];
const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "—");
const methods = (u: AdminUser) => [u.has_password && "Mot de passe", u.has_google && "Google"].filter(Boolean).join(", ") || "—";

export function UsersCard() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const q = useDebouncedValue(search.trim(), 300);
  const [sort, setSort] = useState<Sort>("created_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [deleting, setDeleting] = useState<AdminUser | null>(null);
  const users = useQuery({
    queryKey: ["admin-users", q, sort, order, page],
    queryFn: () => apiGet<AdminUserList>("/api/admin/users", { q, sort, order, page }),
    placeholderData: keepPreviousData,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  const premium = useMutation({
    mutationFn: (u: AdminUser) => apiSend("PATCH", `/api/admin/users/${u.id}`, { is_premium: !u.is_premium }),
    onSettled: refresh,
  });
  const sortBy = (key: Sort) => {
    setOrder(key === sort && order === "asc" ? "desc" : "asc");
    setSort(key);
    setPage(1);
  };
  const data = users.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Utilisateurs{data ? ` (${data.total})` : ""}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input type="search" aria-label="Rechercher un utilisateur" placeholder="Mail, nom ou prénom…" className="w-96 max-w-full bg-white"
               value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <Table>
          <TableHeader>
            <TableRow>
              {COLUMNS.map(({ key, label }) => (
                <TableHead key={key} aria-sort={sort === key ? (order === "asc" ? "ascending" : "descending") : undefined}>
                  <button type="button" className="inline-flex items-center gap-1" onClick={() => sortBy(key)}>
                    {label}
                    {sort === key && (order === "asc" ? <ArrowUp className="size-3" aria-hidden /> : <ArrowDown className="size-3" aria-hidden />)}
                  </button>
                </TableHead>
              ))}
              <TableHead>Connexion</TableHead>
              <TableHead><span className="sr-only">Actions</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.map((u) => {
              const name = `${u.first_name} ${u.last_name}`;
              return (
                <TableRow key={u.id}>
                  <TableCell>{u.first_name}</TableCell>
                  <TableCell>{u.last_name}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>{u.role === "admin" ? "Admin" : "Utilisateur"}</TableCell>
                  <TableCell>
                    <input type="checkbox" role="switch" aria-label={`Premium pour ${name}`} className="size-4 accent-primary"
                           checked={u.is_premium || u.role === "admin"} disabled={u.role === "admin" || premium.isPending}
                           onChange={() => premium.mutate(u)} />
                  </TableCell>
                  <TableCell>{u.verified ? "Oui" : "Non"}</TableCell>
                  <TableCell>{date(u.created_at)}</TableCell>
                  <TableCell>{date(u.last_login_at)}</TableCell>
                  <TableCell>{methods(u)}</TableCell>
                  <TableCell className="space-x-2 whitespace-nowrap text-right">
                    <Button size="sm" variant="outline" aria-label={`Modifier ${name}`} onClick={() => setEditing(u)}>Modifier</Button>
                    <Button size="sm" variant="outline" aria-label={`Supprimer ${name}`} onClick={() => setDeleting(u)}>Supprimer</Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {data && data.items.length === 0 && <p className="text-sm text-muted-foreground">Aucun utilisateur trouvé.</p>}
        {pages > 1 && (
          <div className="flex items-center gap-3 text-sm">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Précédent</Button>
            <span>Page {page} sur {pages}</span>
            <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Suivant</Button>
          </div>
        )}
      </CardContent>
      <EditUserDialog user={editing} onClose={() => { setEditing(null); refresh(); }} />
      <DeleteUserDialog user={deleting} onClose={() => { setDeleting(null); refresh(); }} />
    </Card>
  );
}
