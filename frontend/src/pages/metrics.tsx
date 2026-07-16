import { useQuery } from "@tanstack/react-query"
import {
  CircleDollarSignIcon,
  InboxIcon,
  UserRoundCheckIcon,
  ZapIcon,
  type LucideIcon,
} from "lucide-react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { PageHeader } from "@/components/page-header"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { statusLabel } from "@/lib/format"

const chartConfig = {
  count: { label: "Cases", color: "var(--chart-1)" },
} satisfies ChartConfig

function percent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`
}

function Kpi({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: LucideIcon
  label: string
  value: string
  hint: string
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardDescription>{label}</CardDescription>
          <div className="flex size-8 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
            <Icon className="size-4" />
          </div>
        </div>
        <CardTitle className="text-3xl font-semibold tracking-tight tabular-nums">
          {value}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  )
}

export function MetricsPage() {
  const { data: metrics, isPending } = useQuery({
    queryKey: ["metrics"],
    queryFn: api.metrics,
    refetchInterval: 30_000,
  })

  if (isPending || !metrics) {
    return (
      <>
        <PageHeader
          title="Metrics"
          description="Live KPIs computed from every case on record."
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
        <Skeleton className="h-80 w-full" />
      </>
    )
  }

  const statusData = Object.entries(metrics.cases_by_status)
    .map(([status, count]) => ({ status: statusLabel(status), count }))
    .sort((a, b) => b.count - a.count)

  return (
    <>
      <PageHeader
        title="Metrics"
        description="Live KPIs computed from every case on record."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          icon={ZapIcon}
          label="Automation rate"
          value={percent(metrics.automation_rate)}
          hint="Completed cases decided without a human"
        />
        <Kpi
          icon={UserRoundCheckIcon}
          label="Override rate"
          value={percent(metrics.override_rate)}
          hint={`Humans disagreed on ${metrics.overridden_cases} of ${metrics.human_decided_cases} decisions`}
        />
        <Kpi
          icon={InboxIcon}
          label="Queue depth"
          value={metrics.human_queue_depth.toLocaleString()}
          hint="Cases waiting for human review"
        />
        <Kpi
          icon={CircleDollarSignIcon}
          label="LLM cost"
          value={`$${metrics.total_token_cost_usd.toFixed(2)}`}
          hint={
            metrics.avg_cost_per_case_usd !== null
              ? `$${metrics.avg_cost_per_case_usd.toFixed(4)} per case · ${metrics.total_tokens.toLocaleString()} tokens`
              : "No cases processed yet"
          }
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cases by status</CardTitle>
          <CardDescription>
            All {metrics.total_cases.toLocaleString()} cases across the pipeline
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-72 w-full">
            <BarChart data={statusData} accessibilityLayer margin={{ top: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="status"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                interval={0}
                angle={-20}
                textAnchor="end"
                height={48}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                width={36}
              />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar
                dataKey="count"
                fill="var(--color-count)"
                radius={[4, 4, 0, 0]}
                maxBarSize={48}
              />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </>
  )
}
