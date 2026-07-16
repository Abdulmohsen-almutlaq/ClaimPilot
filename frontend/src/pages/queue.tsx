import { useQuery } from "@tanstack/react-query"
import { InboxIcon } from "lucide-react"
import { useNavigate } from "react-router"

import { Badge } from "@/components/ui/badge"
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

const REASON_LABELS: Record<string, string> = {
  amount_above_threshold: "Amount above threshold",
  low_confidence: "Low AI confidence",
  qa_failed: "QA check failed",
  amount_unknown: "Amount unknown",
  decision_reject: "AI recommends reject",
  decision_needs_info: "Needs more information",
}

export function QueuePage() {
  const navigate = useNavigate()
  const { data: cases, isPending } = useQuery({
    queryKey: ["queue"],
    queryFn: () => api.listCases("human_queue"),
    refetchInterval: 15_000,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Approval queue</CardTitle>
        <CardDescription>
          Cases the pipeline routed to a human, oldest first. The reason column shows why the
          AI did not decide alone.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : !cases || cases.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <InboxIcon />
              </EmptyMedia>
              <EmptyTitle>Queue is clear</EmptyTitle>
              <EmptyDescription>
                Every submitted claim has been handled. New cases appear here automatically.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Claimant</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Received</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cases.map((c) => (
                <TableRow
                  key={c.case_id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/cases/${c.case_id}`)}
                >
                  <TableCell className="font-medium">{c.claimant_name ?? "Unknown"}</TableCell>
                  <TableCell>{c.claimed_amount ?? "—"}</TableCell>
                  <TableCell>{c.category ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      {c.route_reason ? (REASON_LABELS[c.route_reason] ?? c.route_reason) : "—"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(c.created_at).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
