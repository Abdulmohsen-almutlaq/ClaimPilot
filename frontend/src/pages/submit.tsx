import { useMutation } from "@tanstack/react-query"
import {
  CheckIcon,
  FileTextIcon,
  FileUpIcon,
  UploadIcon,
  XIcon,
} from "lucide-react"
import { useRef, useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import { ApiError, api, type SubmitResult } from "@/lib/api"
import { shortId, statusLabel } from "@/lib/format"
import { cn } from "@/lib/utils"

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function SubmitPage() {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [result, setResult] = useState<SubmitResult | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const submitMutation = useMutation({
    mutationFn: (f: File) => api.submitCase(f),
    onSuccess: (res) => {
      setResult(res)
      setFile(null)
      if (!res.created) {
        toast.info("This document was already submitted", {
          description: `It belongs to case #${shortId(res.case_id)}.`,
        })
      }
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Upload failed")
    },
  })

  function pick(candidate: File | undefined | null) {
    if (!candidate) return
    const isPdf =
      candidate.type === "application/pdf" ||
      candidate.name.toLowerCase().endsWith(".pdf")
    if (!isPdf) {
      toast.error("Only PDF documents are accepted")
      return
    }
    setResult(null)
    setFile(candidate)
  }

  return (
    <>
      <PageHeader
        title="Submit a claim"
        description="Upload a claim document as PDF. The pipeline extracts the details, validates the policy, and drafts a decision — small confident claims are decided automatically, the rest go to a reviewer."
      />

      {result ? (
        <SubmittedPanel result={result} onReset={() => setResult(null)} />
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-4">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragging(false)
                pick(e.dataTransfer.files[0])
              }}
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-colors outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
                dragging
                  ? "border-primary bg-primary/5"
                  : "border-border hover:bg-muted/50"
              )}
            >
              <div className="flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <FileUpIcon className="size-5" />
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-sm font-medium">
                  Drop a claim PDF here, or click to browse
                </span>
                <span className="text-xs text-muted-foreground">
                  One PDF per claim · resubmitting the same document is detected
                  automatically
                </span>
              </div>
            </button>
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => {
                pick(e.target.files?.[0])
                e.target.value = ""
              }}
            />

            {file && (
              <div className="flex items-center gap-3 rounded-lg border p-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                  <FileTextIcon className="size-4" />
                </div>
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-sm font-medium">
                    {file.name}
                  </span>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {formatFileSize(file.size)}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Remove file"
                  disabled={submitMutation.isPending}
                  onClick={() => setFile(null)}
                >
                  <XIcon />
                </Button>
              </div>
            )}

            <Button
              className="self-end"
              disabled={!file || submitMutation.isPending}
              onClick={() => file && submitMutation.mutate(file)}
            >
              {submitMutation.isPending ? (
                <Spinner data-icon="inline-start" />
              ) : (
                <UploadIcon data-icon="inline-start" />
              )}
              Submit claim
            </Button>
          </CardContent>
        </Card>
      )}
    </>
  )
}

function SubmittedPanel({
  result,
  onReset,
}: {
  result: SubmitResult
  onReset: () => void
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
        <div className="flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <CheckIcon className="size-5" />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-lg font-semibold tracking-tight">
            {result.created ? "Claim submitted" : "Already submitted"}
          </span>
          <p className="max-w-md text-sm text-muted-foreground">
            Case{" "}
            <span className="font-mono text-foreground">
              #{shortId(result.case_id)}
            </span>{" "}
            {result.created
              ? "is queued. The pipeline is processing it now — it will be decided automatically or routed to a reviewer."
              : `already exists for this document (${statusLabel(result.status)}).`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button render={<Link to={`/cases/${result.case_id}`} />}>
            View case
          </Button>
          <Button variant="outline" onClick={onReset}>
            Submit another
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
