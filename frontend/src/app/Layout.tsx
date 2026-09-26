import { Outlet } from "react-router";
import { Sidebar } from "./Sidebar";

export function Layout() {
  return (
    <div className="min-h-screen min-w-[1280px] bg-background text-foreground">
      <Sidebar />
      <main className="ml-60 px-8 py-6">
        <div className="mx-auto max-w-[1400px]">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
