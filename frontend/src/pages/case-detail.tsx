import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeftIcon, CheckIcon, XIcon } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
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
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { ApiError, api, type HumanDecision } from "@/lib/api"

const FIELD_LABELS: Record<string, string> = {
  claimant_name: "Claimant",
  policy_number: "Policy number",
  incident_date: "Incident date",
  claimed_amount: "Claimed amount",
  category: "Category",
  description: "Description",
}

const QA_LABELS: Record<string, string> = {
  claims_supported: "Claims supported by evidence",
  citations_relevant: "Citations relevant",
  decision_consistent: "Decision consistent",
  professional_tone: "Professional tone",
}

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "approved" || status === "auto_approved") return "default"
  if (status === "rejected") return "destructive"
  return "secondary"
}

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [notes, setNotes] = useState("")

  const { data: detail, isPending } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api.getCase(caseId!),
    enabled: Boolean(caseId),
  })

  const decideMutation = useMutation({
    mutationFn: (decision: HumanDecision) => api.decide(caseId!, decision, notes),
    onSuccess: (result) => {
      toast.success(
        result.overridden
          ? `Case ${result.status} — this overrides the AI recommendation`
          : `Case ${result.status}`
      )
      queryClient.invalidateQueries({ queryKey: ["queue"] })
      queryClient.invalidateQueries({ queryKey: ["case", caseId] })
      navigate("/")
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Decision failed")
    },
  })

  if (isPending || !detail) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  const draft = detail.draft ?? {}
  const fields = detail.extracted_fields ?? {}
  const qa = detail.qa_result ?? {}
  const awaitingDecision = detail.status === "human_queue"

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
          <ArrowLeftIcon data-icon="inline-start" />
          Queue
        </Button>
        <h1 className="truncate font-mono text-sm text-muted-foreground">{detail.case_id}</h1>
        <Badge variant={statusVariant(detail.status)}>{detail.status}</Badge>
        {detail.route_reason && <Badge variant="outline">{detail.route_reason}</Badge>}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Extracted claim</CardTitle>
            <CardDescription>What the AI read from the submitted document</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="flex flex-col gap-2 text-sm">
              {Object.entries(FIELD_LABELS).map(([key, label]) => (
                <div key={key} className="flex justify-between gap-4">
                  <dt className="shrink-0 text-muted-foreground">{label}</dt>
                  <dd className="text-end">{String(fields[key] ?? "—")}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quality checks</CardTitle>
            <CardDescription>The QA model’s rubric on the draft</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2 text-sm">
              {Object.entries(QA_LABELS).map(([key, label]) => {
                const value = qa[key as keyof typeof qa]
                if (value === undefined) return null
                return (
                  <li key={key} className="flex items-center gap-2">
                    {value ? (
                      <CheckIcon className="text-primary" />
                    ) : (
                      <XIcon className="text-destructive" />
                    )}
                    {label}
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            AI draft decision
            {draft.decision && (
              <Badge variant={draft.decision === "approve" ? "default" : "destructive"}>
                {draft.decision}
              </Badge>
            )}
            {draft.confidence !== undefined && (
              <Badge variant="outline">{Math.round(draft.confidence * 100)}% confident</Badge>
            )}
          </CardTitle>
          {draft.payout_amount != null && (
            <CardDescription>Proposed payout: {String(draft.payout_amount)}</CardDescription>
          )}
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {draft.reasoning && <p className="text-sm leading-relaxed">{draft.reasoning}</p>}
          {draft.citations && draft.citations.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">Policy citations</span>
              <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                {draft.citations.map((citation, i) => (
                  <li key={i} className="border-s-2 ps-3">
                    {citation}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {awaitingDecision ? (
        <Card>
          <CardHeader>
            <CardTitle>Your decision</CardTitle>
            <CardDescription>
              Recorded in the immutable audit log under your name. Deciding against the AI
              draft is tracked as an override.
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
              />
              <FieldDescription>Required by policy when overriding the AI.</FieldDescription>
            </Field>
            <div className="flex gap-3">
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
      ) : (
        detail.human_decision && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Decision recorded
                {detail.overridden && <Badge variant="destructive">override</Badge>}
              </CardTitle>
              <CardDescription>
                {detail.human_decision} by {detail.decided_by}
                {detail.decided_at && ` on ${new Date(detail.decided_at).toLocaleString()}`}
              </CardDescription>
            </CardHeader>
          </Card>
        )
      )}

      <div className="text-sm text-muted-foreground">
        Need the full trail?{" "}
        <Link to="/" className="underline underline-offset-4">
          Back to queue
        </Link>
      </div>
    </div>
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

  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button
            variant={decision === "approve" ? "default" : "destructive"}
            disabled={pending}
          >
            {pending && <Spinner data-icon="inline-start" />}
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
