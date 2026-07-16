import { useQuery } from "@tanstack/react-query"
import { ChevronRightIcon, InboxIcon } from "lucide-react"
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
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import {
  formatAmount,
  formatDateTime,
  formatRelativeTime,
  reasonLabel,
  shortId,
} from "@/lib/format"

export function QueuePage() {
  const navigate = useNavigate()
  const { data: cases, isPending } = useQuery({
    queryKey: ["queue"],
    queryFn: () => api.listCases("human_queue"),
    refetchInterval: 15_000,
  })

  return (
    <>
      <PageHeader
        title={
          <>
            Approval queue
            {cases && cases.length > 0 && (
              <Badge variant="secondary" className="tabular-nums">
                {cases.length} waiting
              </Badge>
            )}
          </>
        }
        description="Cases the pipeline routed to a human, oldest first. The reason column shows why the AI did not decide alone."
      />

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
                  <InboxIcon />
                </EmptyMedia>
                <EmptyTitle>Queue is clear</EmptyTitle>
                <EmptyDescription>
                  Every submitted claim has been handled. New cases appear here
                  automatically.
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
                  <TableHead>Reason</TableHead>
                  <TableHead>Waiting</TableHead>
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
                      <Badge variant="secondary">
                        {reasonLabel(c.route_reason)}
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
