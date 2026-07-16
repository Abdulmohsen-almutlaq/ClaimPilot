const API_BASE = "/api"
const TOKEN_KEY = "claimpilot_token"

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set("Content-Type", "application/json")
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers })

  if (resp.status === 401) {
    clearToken()
    window.location.assign("/login")
    throw new ApiError(401, "Session expired")
  }
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = (await resp.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(resp.status, detail)
  }
  return (await resp.json()) as T
}

export interface Me {
  email: string
  role: string
}

export interface CaseSummary {
  case_id: string
  status: string
  route_reason: string | null
  claimant_name: string | null
  claimed_amount: string | null
  category: string | null
  created_at: string
}

export interface CaseDetail {
  case_id: string
  status: string
  extracted_fields: Record<string, unknown> | null
  validation_result: Record<string, unknown> | null
  draft: {
    decision?: "approve" | "reject" | "needs_info"
    payout_amount?: string | null
    reasoning?: string
    citations?: string[]
    confidence?: number
  } | null
  qa_result: {
    passed?: boolean
    claims_supported?: boolean
    citations_relevant?: boolean
    decision_consistent?: boolean
    professional_tone?: boolean
  } | null
  route: string | null
  route_reason: string | null
  human_decision: string | null
  overridden: boolean | null
  decided_by: string | null
  decided_at: string | null
}

export type HumanDecision = "approve" | "reject"

export interface DecisionResult {
  case_id: string
  status: string
  human_decision: string
  ai_decision: string | null
  overridden: boolean
}

export interface Metrics {
  total_cases: number
  cases_by_status: Record<string, number>
  human_queue_depth: number
  automation_rate: number | null
  override_rate: number | null
  human_decided_cases: number
  overridden_cases: number
  total_tokens: number
  total_token_cost_usd: number
  avg_tokens_per_case: number | null
  avg_cost_per_case_usd: number | null
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<Me>("/auth/me"),
  listCases: (status: string) => request<CaseSummary[]>(`/cases?status=${status}`),
  getCase: (caseId: string) => request<CaseDetail>(`/cases/${caseId}`),
  decide: (caseId: string, decision: HumanDecision, notes: string) =>
    request<DecisionResult>(`/cases/${caseId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes: notes || null }),
    }),
  metrics: () => request<Metrics>("/metrics"),
}
