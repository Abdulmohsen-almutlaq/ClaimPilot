import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeftIcon, CheckIcon, HistoryIcon, XIcon } from "lucide-react"
import { useState } from "react"
import { useNavigate, useParams } from "react-router"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  ApiError,
  api,
  type AuditEntry,
  type CaseDetail,
  type HumanDecision,
} from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  formatAmount,
  formatDateTime,
  reasonLabel,
  shortId,
  statusLabel,
} from "@/lib/format"

const QA_LABELS: Record<string, string> = {
  claims_supported: "Claims supported by evidence",
  citations_relevant: "Citations relevant",
  decision_consistent: "Decision consistent",
  professional_tone: "Professional tone",
}

function statusVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "approved" || status === "auto_approved") return "default"
  if (status === "rejected") return "destructive"
  return "secondary"
}

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()

  const { data: detail, isPending } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api.getCase(caseId!),
    enabled: Boolean(caseId),
  })
  // Same query key as the layout header, so this is served from cache. The
  // audit endpoint is approver/admin-only — hide the tab from submitters.
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me })
  const canViewAudit = me?.role === "approver" || me?.role === "admin"

  if (isPending || !detail) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-9 w-72" />
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="flex flex-col gap-6 lg:col-span-2">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-56 w-full" />
          </div>
          <Skeleton className="h-72 w-full" />
        </div>
      </div>
    )
  }

  const draft = detail.draft ?? {}
  const fields = detail.extracted_fields ?? {}
  const claimant =
    typeof fields.claimant_name === "string"
      ? fields.claimant_name
      : "Unknown claimant"

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="self-start text-muted-foreground"
          onClick={() => navigate("/")}
        >
          <ArrowLeftIcon data-icon="inline-start" />
          Back to queue
        </Button>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{claimant}</h1>
          <Badge variant={statusVariant(detail.status)}>
            {statusLabel(detail.status)}
          </Badge>
          {detail.route_reason && (
            <Badge variant="outline">{reasonLabel(detail.route_reason)}</Badge>
          )}
          <span
            className="font-mono text-xs text-muted-foreground"
            title={detail.case_id}
          >
            #{shortId(detail.case_id)}
          </span>
        </div>
      </div>

      <Tabs defaultValue="review" className="gap-6">
        {canViewAudit && (
          <TabsList>
            <TabsTrigger value="review">Review</TabsTrigger>
            <TabsTrigger value="audit">Audit trail</TabsTrigger>
          </TabsList>
        )}
        <TabsContent value="review">
          <div className="grid items-start gap-6 lg:grid-cols-3">
            <div className="flex flex-col gap-6 lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle>Extracted claim</CardTitle>
                  <CardDescription>
                    What the AI read from the submitted document
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
                    <ClaimField label="Claimed amount" emphasis>
                      {formatAmount(fields.claimed_amount as string | null)}
                    </ClaimField>
                    <ClaimField label="Category">
                      <span className="capitalize">
                        {String(fields.category ?? "—")}
                      </span>
                    </ClaimField>
                    <ClaimField label="Policy number">
                      {String(fields.policy_number ?? "—")}
                    </ClaimField>
                    <ClaimField label="Incident date">
                      {String(fields.incident_date ?? "—")}
                    </ClaimField>
                    <div className="flex flex-col gap-1 sm:col-span-2">
                      <dt className="text-muted-foreground">Description</dt>
                      <dd className="leading-relaxed">
                        {String(fields.description ?? "—")}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>

              <EvidenceCard detail={detail} />

              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    AI draft decision
                    {draft.decision && (
                      <Badge
                        variant={
                          draft.decision === "approve"
                            ? "default"
                            : "destructive"
                        }
                      >
                        {draft.decision}
                      </Badge>
                    )}
                  </CardTitle>
                  {draft.payout_amount != null && (
                    <CardDescription>
                      Proposed payout:{" "}
                      {formatAmount(String(draft.payout_amount))}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  {draft.reasoning && (
                    <p className="text-sm leading-relaxed text-foreground/90">
                      {draft.reasoning}
                    </p>
                  )}
                  {draft.citations && draft.citations.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <span className="text-sm font-medium">Cited clauses</span>
                      <div className="flex flex-wrap gap-1.5">
                        {draft.citations.map((citation, i) => (
                          <Badge
                            key={i}
                            variant="outline"
                            className="font-mono"
                          >
                            {citation}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {draft.confidence !== undefined && (
                    <>
                      <Separator />
                      <div className="flex flex-col gap-1.5">
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">
                            Model confidence
                          </span>
                          <span className="font-medium tabular-nums">
                            {Math.round(draft.confidence * 100)}%
                          </span>
                        </div>
                        <Progress value={draft.confidence * 100} />
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="flex flex-col gap-6 lg:sticky lg:top-20">
              <QaCard detail={detail} />
              <DecisionPanel detail={detail} />
            </div>
          </div>
        </TabsContent>
        {canViewAudit && (
          <TabsContent value="audit">
            <AuditTrailCard caseId={detail.case_id} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}

function ClaimField({
  label,
  emphasis,
  children,
}: {
  label: string
  emphasis?: boolean
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-muted-foreground">{label}</dt>
      <dd
        className={
          emphasis ? "text-base font-semibold tabular-nums" : undefined
        }
      >
        {children}
      </dd>
    </div>
  )
}

function EvidenceCard({ detail }: { detail: CaseDetail }) {
  const validation = detail.validation_result
  const clauses = detail.evidence
  if (!validation && clauses == null) return null

  // Citations are clause ids, but tolerate the model wrapping them in prose
  // ("per clause AUTO-001") — an approver must see which sources were used.
  const citations = detail.draft?.citations ?? []
  const isCited = (clauseId: string) =>
    citations.some((c) => c === clauseId || c.includes(clauseId))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Evidence the AI relied on</CardTitle>
        <CardDescription>
          CRM validation and the policy clauses retrieved as grounds for the
          draft
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {validation && (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
              <span>CRM validation</span>
              <Badge variant={validation.valid ? "default" : "destructive"}>
                {validation.valid ? "valid" : "invalid"}
              </Badge>
              {validation.policy_status && (
                <Badge variant="outline" className="capitalize">
                  policy {validation.policy_status}
                </Badge>
              )}
            </div>
            {validation.reasons && validation.reasons.length > 0 && (
              <ul className="flex list-disc flex-col gap-1.5 ps-5 text-sm text-muted-foreground">
                {validation.reasons.map((reason, i) => (
                  <li key={i} className="leading-relaxed">
                    {reason}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {validation && clauses != null && <Separator />}
        {clauses != null && (
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium">
              Retrieved policy clauses
            </span>
            {clauses.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No policy clauses passed the relevance threshold — the draft is
                not grounded in retrieved policy text.
              </p>
            ) : (
              clauses.map((clause) => (
                <figure
                  key={clause.clause_id}
                  className="flex flex-col gap-2 rounded-lg border p-3"
                >
                  <figcaption className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="font-mono">
                      {clause.clause_id}
                    </Badge>
                    {isCited(clause.clause_id) && (
                      <Badge variant="secondary">
                        <CheckIcon data-icon="inline-start" />
                        Cited in draft
                      </Badge>
                    )}
                    <span className="ms-auto text-xs text-muted-foreground tabular-nums">
                      {Math.round(clause.similarity * 100)}% relevance
                    </span>
                  </figcaption>
                  <blockquote className="text-sm leading-relaxed text-foreground/90">
                    {clause.text}
                  </blockquote>
                </figure>
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AuditTrailCard({ caseId }: { caseId: string }) {
  const { data: trail, isPending } = useQuery({
    queryKey: ["audit", caseId],
    queryFn: () => api.getAudit(caseId),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit trail</CardTitle>
        <CardDescription>
          Append-only record of every pipeline step and human action on this
          case
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : !trail || trail.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <HistoryIcon />
              </EmptyMedia>
              <EmptyTitle>No audit events</EmptyTitle>
              <EmptyDescription>
                Nothing has been recorded for this case yet.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ol className="flex flex-col">
            {trail.map((entry, i) => (
              <AuditTimelineItem
                key={entry.id}
                entry={entry}
                isLast={i === trail.length - 1}
              />
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}

function eventVariant(
  eventType: string
): "default" | "secondary" | "destructive" | "outline" {
  if (eventType === "human_decision") return "default"
  if (eventType.includes("failed") || eventType.includes("error"))
    return "destructive"
  return "secondary"
}

function AuditTimelineItem({
  entry,
  isLast,
}: {
  entry: AuditEntry
  isLast: boolean
}) {
  // The compliance story: which model and prompt version produced this step.
  const meta: string[] = []
  if (entry.model) meta.push(entry.model)
  if (entry.model_version) meta.push(`model ${entry.model_version}`)
  if (entry.prompt_version) meta.push(`prompt ${entry.prompt_version}`)
  if (entry.latency_ms != null) meta.push(`${entry.latency_ms} ms`)
  if (entry.cost_usd != null) meta.push(`$${entry.cost_usd}`)

  const payload = entry.payload ?? {}

  return (
    <li className="relative flex gap-3">
      <div className="flex flex-col items-center">
        <span className="mt-1 size-2 shrink-0 rounded-full border-2 border-primary/60 bg-background" />
        {!isLast && <span className="w-px flex-1 bg-border" />}
      </div>
      <div
        className={cn("flex min-w-0 flex-1 flex-col gap-1", !isLast && "pb-5")}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={eventVariant(entry.event_type)}>
            {entry.event_type.replaceAll("_", " ")}
          </Badge>
          {entry.node && (
            <span className="font-mono text-xs text-muted-foreground">
              {entry.node}
            </span>
          )}
          <span className="ms-auto text-xs text-muted-foreground tabular-nums">
            {formatDateTime(entry.timestamp)}
          </span>
        </div>
        <span className="text-sm text-foreground/90">{entry.actor}</span>
        {meta.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {meta.join(" · ")}
          </span>
        )}
        {entry.event_type === "human_decision" && (
          <div className="mt-1 flex flex-col gap-1.5 rounded-md border p-2.5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium capitalize">
                {String(payload.decision ?? "—")}
              </span>
              {payload.overridden === true && (
                <Badge variant="destructive">override</Badge>
              )}
              {typeof payload.ai_decision === "string" && (
                <span className="text-xs text-muted-foreground">
                  AI recommended {payload.ai_decision}
                </span>
              )}
            </div>
            {typeof payload.notes === "string" && payload.notes && (
              <p className="leading-relaxed text-muted-foreground">
                {payload.notes}
              </p>
            )}
          </div>
        )}
      </div>
    </li>
  )
}

function QaCard({ detail }: { detail: CaseDetail }) {
  const qa = detail.qa_result ?? {}
  const entries = Object.entries(QA_LABELS).filter(
    ([key]) => qa[key as keyof typeof qa] !== undefined
  )
  if (entries.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Quality checks
          {qa.passed !== undefined && (
            <Badge variant={qa.passed ? "default" : "destructive"}>
              {qa.passed ? "passed" : "failed"}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-2.5 text-sm">
          {entries.map(([key, label]) => {
            const value = qa[key as keyof typeof qa]
            return (
              <li key={key} className="flex items-center gap-2.5">
                {value ? (
                  <CheckIcon className="size-4 shrink-0 text-primary" />
                ) : (
                  <XIcon className="size-4 shrink-0 text-destructive" />
                )}
                <span className={value ? undefined : "text-muted-foreground"}>
                  {label}
                </span>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

function DecisionPanel({ detail }: { detail: CaseDetail }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [notes, setNotes] = useState("")
  const draft = detail.draft ?? {}

  const decideMutation = useMutation({
    mutationFn: (decision: HumanDecision) =>
      api.decide(detail.case_id, decision, notes),
    onSuccess: (result) => {
      toast.success(
        result.overridden
          ? `Case ${statusLabel(result.status).toLowerCase()} — this overrides the AI recommendation`
          : `Case ${statusLabel(result.status).toLowerCase()}`
      )
      queryClient.invalidateQueries({ queryKey: ["queue"] })
      queryClient.invalidateQueries({ queryKey: ["case", detail.case_id] })
      navigate("/")
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Decision failed")
    },
  })

  if (detail.status !== "human_queue") {
    if (!detail.human_decision) return null
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Decision recorded
            {detail.overridden && <Badge variant="destructive">override</Badge>}
          </CardTitle>
          <CardDescription>
            {statusLabel(detail.status)} by {detail.decided_by}
            {detail.decided_at && ` · ${formatDateTime(detail.decided_at)}`}
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Card className="border-primary/20">
      <CardHeader>
        <CardTitle>Your decision</CardTitle>
        <CardDescription>
          Recorded in the immutable audit log under your name. Deciding against
          the AI draft is tracked as an override.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Field>
          <FieldLabel htmlFor="notes">Notes</FieldLabel>
          <Textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional justification, visible in the audit trail"
            rows={3}
          />
          <FieldDescription>
            Required by policy when overriding the AI.
          </FieldDescription>
        </Field>
        <div className="flex flex-col gap-2">
          <ConfirmDecision
            decision="approve"
            aiDecision={draft.decision}
            pending={decideMutation.isPending}
            onConfirm={() => decideMutation.mutate("approve")}
          />
          <ConfirmDecision
            decision="reject"
            aiDecision={draft.decision}
            pending={decideMutation.isPending}
            onConfirm={() => decideMutation.mutate("reject")}
          />
        </div>
      </CardContent>
    </Card>
  )
}

function ConfirmDecision({
  decision,
  aiDecision,
  pending,
  onConfirm,
}: {
  decision: HumanDecision
  aiDecision: string | undefined
  pending: boolean
  onConfirm: () => void
}) {
  const isOverride = aiDecision !== undefined && aiDecision !== decision
  const label = decision === "approve" ? "Approve claim" : "Reject claim"
  const Icon = decision === "approve" ? CheckIcon : XIcon

  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button
            variant={decision === "approve" ? "default" : "outline"}
            className={
              decision === "reject"
                ? "text-destructive hover:text-destructive"
                : undefined
            }
            disabled={pending}
          >
            {pending ? (
              <Spinner data-icon="inline-start" />
            ) : (
              <Icon data-icon="inline-start" />
            )}
            {label}
          </Button>
        }
      />
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{label}?</AlertDialogTitle>
          <AlertDialogDescription>
            {isOverride
              ? `The AI recommended "${aiDecision}". Proceeding records this as an override in the audit log.`
              : "This decision is final and is written to the immutable audit log."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Confirm</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
