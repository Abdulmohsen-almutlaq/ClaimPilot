import { useQuery } from "@tanstack/react-query"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

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

const chartConfig = {
  count: { label: "Cases", color: "var(--chart-1)" },
} satisfies ChartConfig

function percent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`
}

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl tabular-nums">{value}</CardTitle>
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
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-36 w-full" />
        ))}
      </div>
    )
  }

  const statusData = Object.entries(metrics.cases_by_status)
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => b.count - a.count)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Automation rate"
          value={percent(metrics.automation_rate)}
          hint="Completed cases decided without a human"
        />
        <Kpi
          label="Override rate"
          value={percent(metrics.override_rate)}
          hint={`Humans disagreed with the AI on ${metrics.overridden_cases} of ${metrics.human_decided_cases} decisions`}
        />
        <Kpi
          label="Queue depth"
          value={String(metrics.human_queue_depth)}
          hint="Cases waiting for human review"
        />
        <Kpi
          label="LLM cost"
          value={`$${metrics.total_token_cost_usd.toFixed(2)}`}
          hint={
            metrics.avg_cost_per_case_usd !== null
              ? `$${metrics.avg_cost_per_case_usd.toFixed(4)} per case, ${metrics.total_tokens.toLocaleString()} tokens`
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
          <ChartContainer config={chartConfig} className="h-64 w-full">
            <BarChart data={statusData} accessibilityLayer>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="status" tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={32} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="count" fill="var(--color-count)" radius={4} />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  )
}
