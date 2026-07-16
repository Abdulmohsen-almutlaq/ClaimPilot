import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ChevronRightIcon, SearchXIcon } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router"

import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { api } from "@/lib/api"
import {
  formatAmount,
  formatDateTime,
  formatRelativeTime,
  shortId,
  statusLabel,
} from "@/lib/format"

const STATUS_FILTERS = [
  "all",
  "human_queue",
  "auto_approved",
  "approved",
  "rejected",
  "needs_info",
  "error",
] as const

function statusVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "approved" || status === "auto_approved") return "default"
  if (status === "rejected" || status === "error") return "destructive"
  return "secondary"
}

export function AllCasesPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<string>("all")
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q.trim()), 300)
    return () => clearTimeout(timer)
  }, [q])

  const { data: cases, isPending } = useQuery({
    queryKey: ["cases", status, debouncedQ],
    queryFn: () =>
      api.listAllCases({
        status: status === "all" ? undefined : status,
        q: debouncedQ || undefined,
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <PageHeader
        title="All cases"
        description="Every case in the system, newest first — including decided ones that have left the approval queue."
      />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search claimant or policy number…"
          aria-label="Search cases"
          className="max-w-xs"
        />
        <ToggleGroup
          value={[status]}
          onValueChange={(value) => setStatus((value[0] as string) ?? "all")}
          variant="outline"
          size="sm"
          className="flex-wrap"
        >
          {STATUS_FILTERS.map((s) => (
            <ToggleGroupItem key={s} value={s}>
              {s === "all" ? "All" : statusLabel(s)}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>

      <Card className="py-0">
        <CardContent className="px-0">
          {isPending ? (
            <div className="flex flex-col gap-3 p-6">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-2/3" />
            </div>
          ) : !cases || cases.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <SearchXIcon />
                </EmptyMedia>
                <EmptyTitle>No matching cases</EmptyTitle>
                <EmptyDescription>
                  Try a different search term or status filter.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="ps-6">Case</TableHead>
                  <TableHead>Claimant</TableHead>
                  <TableHead className="text-end">Amount</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {cases.map((c) => (
                  <TableRow
                    key={c.case_id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/cases/${c.case_id}`)}
                  >
                    <TableCell className="ps-6 font-mono text-xs text-muted-foreground">
                      {shortId(c.case_id)}
                    </TableCell>
                    <TableCell className="font-medium">
                      {c.claimant_name ?? (
                        <span className="text-muted-foreground">Unknown</span>
                      )}
                    </TableCell>
                    <TableCell className="text-end tabular-nums">
                      {formatAmount(c.claimed_amount)}
                    </TableCell>
                    <TableCell className="capitalize">
                      {c.category ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(c.status)}>
                        {statusLabel(c.status)}
                      </Badge>
                    </TableCell>
                    <TableCell
                      className="text-muted-foreground"
                      title={formatDateTime(c.created_at)}
                    >
                      {formatRelativeTime(c.created_at)}
                    </TableCell>
                    <TableCell className="pe-4 text-muted-foreground">
                      <ChevronRightIcon className="size-4" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  )
}
