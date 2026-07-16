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

async function send(
  path: string,
  init: RequestInit | undefined,
  json: boolean
): Promise<Response> {
  const headers = new Headers(init?.headers)
  // FormData bodies must not get a manual Content-Type — the browser sets
  // the multipart boundary itself.
  if (json) headers.set("Content-Type", "application/json")
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
  return resp
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await send(path, init, true)
  if (resp.status === 204) return undefined as T
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

export interface ValidationResult {
  valid?: boolean
  reasons?: string[]
  policy_status?: string | null
}

export interface EvidenceClause {
  clause_id: string
  text: string
  similarity: number
}

export interface CaseDetail {
  case_id: string
  status: string
  extracted_fields: Record<string, unknown> | null
  validation_result: ValidationResult | null
  evidence: EvidenceClause[] | null
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

export interface AuditEntry {
  id: string
  timestamp: string
  actor: string
  event_type: string
  node: string | null
  model: string | null
  model_version: string | null
  prompt_version: string | null
  input_hash: string | null
  output_hash: string | null
  payload: Record<string, unknown> | null
  cost_usd: string | null
  latency_ms: number | null
}

export interface SubmitResult {
  case_id: string
  status: string
  /** false when this document was already submitted (201 new vs 200 duplicate) */
  created: boolean
}

export interface DlqEntry {
  case_id: string
  error: string
  traceback: string
  failed_at: string
}

export interface AdminUser {
  id: string
  email: string
  role: string
  created_at: string
}

export interface TrackResult {
  case_id: string
  phase: string
  submitted_at: string
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
  listCases: (status: string) =>
    request<CaseSummary[]>(`/cases?status=${status}`),
  listAllCases: (params: { status?: string; q?: string }) => {
    const search = new URLSearchParams({ order: "desc", limit: "200" })
    if (params.status) search.set("status", params.status)
    if (params.q) search.set("q", params.q)
    return request<CaseSummary[]>(`/cases?${search.toString()}`)
  },
  getCase: (caseId: string) => request<CaseDetail>(`/cases/${caseId}`),
  getAudit: (caseId: string) => request<AuditEntry[]>(`/cases/${caseId}/audit`),
  submitCase: async (file: File): Promise<SubmitResult> => {
    const form = new FormData()
    form.append("file", file)
    const resp = await send("/cases", { method: "POST", body: form }, false)
    const body = (await resp.json()) as { case_id: string; status: string }
    return { ...body, created: resp.status === 201 }
  },
  decide: (caseId: string, decision: HumanDecision, notes: string) =>
    request<DecisionResult>(`/cases/${caseId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes: notes || null }),
    }),
  metrics: () => request<Metrics>("/metrics"),
  listDlq: () => request<DlqEntry[]>("/admin/dlq"),
  requeueDlq: (caseId: string) =>
    request<{ case_id: string; status: string }>(
      `/admin/dlq/${caseId}/requeue`,
      { method: "POST" }
    ),
  listUsers: () => request<AdminUser[]>("/admin/users"),
  createUser: (payload: { email: string; password: string; role: string }) =>
    request<AdminUser>("/admin/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateUserRole: (id: string, role: string) =>
    request<AdminUser>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  deleteUser: (id: string) =>
    request<void>(`/admin/users/${id}`, { method: "DELETE" }),
  trackCase: (caseId: string, policyNumber: string) =>
    request<TrackResult>(
      `/track/${caseId.trim()}?policy_number=${encodeURIComponent(policyNumber.trim())}`
    ),
}
