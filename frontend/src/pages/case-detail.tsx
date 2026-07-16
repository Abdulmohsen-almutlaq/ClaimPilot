import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeftIcon, CheckIcon, XIcon } from "lucide-react"
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
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { ApiError, api, type CaseDetail, type HumanDecision } from "@/lib/api"
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

  if (isPending || !detail) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-9 w-72" />
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="flex flex-col gap-6 lg:col-span-2">
            <Skeleton className="h-48 w-full" />
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

          <Card>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2">
                AI draft decision
                {draft.decision && (
                  <Badge
                    variant={
                      draft.decision === "approve" ? "default" : "destructive"
                    }
                  >
                    {draft.decision}
                  </Badge>
                )}
              </CardTitle>
              {draft.payout_amount != null && (
                <CardDescription>
                  Proposed payout: {formatAmount(String(draft.payout_amount))}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {draft.confidence !== undefined && (
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
              )}
              {draft.reasoning && (
                <p className="text-sm leading-relaxed text-foreground/90">
                  {draft.reasoning}
                </p>
              )}
              {draft.citations && draft.citations.length > 0 && (
                <div className="flex flex-col gap-2">
                  <Separator />
                  <span className="text-sm font-medium">Policy citations</span>
                  <ul className="flex flex-col gap-2 text-sm text-muted-foreground">
                    {draft.citations.map((citation, i) => (
                      <li
                        key={i}
                        className="border-s-2 border-primary/40 ps-3 leading-relaxed"
                      >
                        {citation}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-6 lg:sticky lg:top-20">
          <QaCard detail={detail} />
          <DecisionPanel detail={detail} />
        </div>
      </div>
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
