import { useQuery } from "@tanstack/react-query"
import { FileCheck2Icon, LogOutIcon, MoonIcon, SunIcon } from "lucide-react"
import { NavLink, Outlet, useNavigate } from "react-router"

import { useTheme } from "@/components/theme-provider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
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
            : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
        )
      }
    >
      {label}
    </NavLink>
  )
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const isDark =
    theme === "dark" ||
    (theme === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches)

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </Button>
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
    <div className="flex min-h-svh flex-col bg-muted/30">
      <header className="sticky top-0 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <FileCheck2Icon className="size-4" />
            </div>
            <span className="text-sm font-semibold tracking-tight">
              ClaimPilot
            </span>
          </div>
          <nav className="flex items-center gap-1">
            {(me?.role === "approver" || me?.role === "admin") && (
              <>
                <NavItem to="/" label="Approval queue" />
                <NavItem to="/cases" label="All cases" />
                <NavItem to="/metrics" label="Metrics" />
              </>
            )}
            {(me?.role === "submitter" || me?.role === "admin") && (
              <NavItem to="/submit" label="Submit claim" />
            )}
          </nav>
          <div className="ms-auto flex items-center gap-2">
            {me && (
              <>
                <div className="hidden items-center gap-2 sm:flex">
                  <span className="text-sm text-muted-foreground">
                    {me.email}
                  </span>
                  <Badge variant="secondary" className="capitalize">
                    {me.role}
                  </Badge>
                </div>
                <Separator
                  orientation="vertical"
                  className="hidden h-5 sm:block"
                />
              </>
            )}
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOutIcon data-icon="inline-start" />
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
