import { useMutation } from "@tanstack/react-query"
import {
  CheckIcon,
  ClockIcon,
  FileSearchIcon,
  InfoIcon,
  SearchIcon,
  XIcon,
} from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

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
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { ApiError, api, type TrackResult } from "@/lib/api"
import { formatDateTime, shortId } from "@/lib/format"

const PHASES: Record<
  string,
  { label: string; note: string; icon: typeof ClockIcon }
> = {
  processing: {
    label: "Processing",
    note: "Your claim has been received and is being processed.",
    icon: ClockIcon,
  },
  in_review: {
    label: "In review",
    note: "Your claim is with a claims specialist for review.",
    icon: FileSearchIcon,
  },
  needs_info: {
    label: "More information needed",
    note: "We need additional documents — your insurer will contact you.",
    icon: InfoIcon,
  },
  approved: {
    label: "Approved",
    note: "Your claim has been approved.",
    icon: CheckIcon,
  },
  rejected: {
    label: "Rejected",
    note: "Your claim was not approved. Contact your insurer for details.",
    icon: XIcon,
  },
}

export function TrackPage() {
  const [caseId, setCaseId] = useState("")
  const [policyNumber, setPolicyNumber] = useState("")
  const [result, setResult] = useState<TrackResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const trackMutation = useMutation({
    mutationFn: () => api.trackCase(caseId, policyNumber),
    onSuccess: (res) => {
      setResult(res)
      setError(null)
    },
    onError: (err) => {
      setResult(null)
      setError(
        err instanceof ApiError && err.status === 404
          ? "No claim matches those details. Check the claim reference and policy number — recently submitted claims can take a minute to appear."
          : "Something went wrong. Try again."
      )
    },
  })

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted/40 p-6">
      <div className="flex flex-col items-center gap-1 text-center">
        <span className="text-lg font-semibold tracking-tight">
          Track your claim
        </span>
        <span className="text-xs text-muted-foreground">
          Enter the claim reference from your submission receipt and your policy
          number
        </span>
      </div>

      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Claim status</CardTitle>
          <CardDescription>
            No account needed — both fields must match.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              trackMutation.mutate()
            }}
          >
            <FieldGroup>
              <Field data-invalid={error ? true : undefined}>
                <FieldLabel htmlFor="track-case">Claim reference</FieldLabel>
                <Input
                  id="track-case"
                  value={caseId}
                  onChange={(e) => setCaseId(e.target.value)}
                  placeholder="e.g. d598fa2c-b1ee-4c6c-84b9-0649aa1a19b6"
                  aria-invalid={error ? true : undefined}
                  required
                />
              </Field>
              <Field data-invalid={error ? true : undefined}>
                <FieldLabel htmlFor="track-policy">Policy number</FieldLabel>
                <Input
                  id="track-policy"
                  value={policyNumber}
                  onChange={(e) => setPolicyNumber(e.target.value)}
                  placeholder="e.g. POL-AUTO-001"
                  aria-invalid={error ? true : undefined}
                  required
                />
                {error && <FieldError>{error}</FieldError>}
              </Field>
              <Button
                type="submit"
                disabled={trackMutation.isPending}
                className="w-full"
              >
                {trackMutation.isPending ? (
                  <Spinner data-icon="inline-start" />
                ) : (
                  <SearchIcon data-icon="inline-start" />
                )}
                Check status
              </Button>
              {result && <StatusPanel result={result} />}
              <FieldDescription className="text-center">
                Insurer staff? <Link to="/login">Sign in</Link>
              </FieldDescription>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

function StatusPanel({ result }: { result: TrackResult }) {
  const phase = PHASES[result.phase] ?? PHASES.processing
  const Icon = phase.icon
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-4">
      <div className="flex items-center gap-2">
        <div className="flex size-8 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="size-4" />
        </div>
        <Badge
          variant={
            result.phase === "approved"
              ? "default"
              : result.phase === "rejected"
                ? "destructive"
                : "secondary"
          }
        >
          {phase.label}
        </Badge>
        <span className="ms-auto font-mono text-xs text-muted-foreground">
          #{shortId(result.case_id)}
        </span>
      </div>
      <p className="text-sm leading-relaxed text-muted-foreground">
        {phase.note}
      </p>
      <p className="text-xs text-muted-foreground">
        Submitted {formatDateTime(result.submitted_at)}
        {result.decided_at && ` · decided ${formatDateTime(result.decided_at)}`}
      </p>
    </div>
  )
}
