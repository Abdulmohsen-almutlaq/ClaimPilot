import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router"

import { Layout } from "@/components/layout"
import { Toaster } from "@/components/ui/sonner"
import { getToken } from "@/lib/api"
import { AllCasesPage } from "@/pages/all-cases"
import { CaseDetailPage } from "@/pages/case-detail"
import { LoginPage } from "@/pages/login"
import { MetricsPage } from "@/pages/metrics"
import { QueuePage } from "@/pages/queue"
import { SubmitPage } from "@/pages/submit"

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

function RequireAuth() {
  if (!getToken()) return <Navigate to="/login" replace />
  return <Outlet />
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route path="/" element={<QueuePage />} />
              <Route path="/cases" element={<AllCasesPage />} />
              <Route path="/cases/:caseId" element={<CaseDetailPage />} />
              <Route path="/metrics" element={<MetricsPage />} />
              <Route path="/submit" element={<SubmitPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  )
}

export default App
