import { useQuery } from "@tanstack/react-query"
import { LogOutIcon } from "lucide-react"
import { NavLink, Outlet, useNavigate } from "react-router"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api, clearToken } from "@/lib/api"
import { cn } from "@/lib/utils"

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          isActive
            ? "bg-secondary text-secondary-foreground"
            : "text-muted-foreground hover:text-foreground"
        )
      }
    >
      {label}
    </NavLink>
  )
}

export function Layout() {
  const navigate = useNavigate()
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me })

  function logout() {
    clearToken()
    navigate("/login")
  }

  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-6 px-4 py-3">
          <span className="text-sm font-semibold tracking-tight">ClaimPilot</span>
          <nav className="flex items-center gap-1">
            <NavItem to="/" label="Approval queue" />
            <NavItem to="/metrics" label="Metrics" />
          </nav>
          <div className="ms-auto flex items-center gap-3">
            {me && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">{me.email}</span>
                <Badge variant="secondary">{me.role}</Badge>
              </div>
            )}
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOutIcon data-icon="inline-start" />
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
