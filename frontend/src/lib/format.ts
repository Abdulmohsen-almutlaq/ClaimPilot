const sar = new Intl.NumberFormat("en", {
  style: "currency",
  currency: "SAR",
  maximumFractionDigits: 0,
})

export function formatAmount(value: string | null | undefined): string {
  if (value == null || value === "") return "—"
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return value
  return sar.format(numeric)
}

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" })

export function formatRelativeTime(iso: string): string {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000
  const abs = Math.abs(seconds)
  if (abs < 60) return relative.format(Math.round(seconds), "second")
  if (abs < 3600) return relative.format(Math.round(seconds / 60), "minute")
  if (abs < 86_400) return relative.format(Math.round(seconds / 3600), "hour")
  return relative.format(Math.round(seconds / 86_400), "day")
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en", {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export function shortId(uuid: string): string {
  return uuid.slice(0, 8)
}

const STATUS_LABELS: Record<string, string> = {
  auto_approved: "Auto-approved",
  human_queue: "In review",
  approved: "Approved",
  rejected: "Rejected",
  needs_info: "Needs info",
  intake: "Intake",
  queued: "Queued",
  drafted: "Drafted",
  error: "Error",
  denied: "Denied",
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status.replaceAll("_", " ")
}

export const REASON_LABELS: Record<string, string> = {
  amount_above_threshold: "Amount above threshold",
  low_confidence: "Low AI confidence",
  qa_failed: "QA check failed",
  amount_unknown: "Amount unknown",
  decision_reject: "AI recommends reject",
  decision_needs_info: "Needs more information",
  budget_exhausted: "Token budget exhausted",
}

export function reasonLabel(reason: string | null): string {
  if (!reason) return "—"
  return REASON_LABELS[reason] ?? reason.replaceAll("_", " ")
}
