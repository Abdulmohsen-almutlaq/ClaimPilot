import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  InboxIcon,
  PlusIcon,
  RotateCcwIcon,
  Trash2Icon,
  UsersIcon,
} from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { PageHeader } from "@/components/page-header"
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
import { Card, CardContent } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ApiError, api, type AdminUser } from "@/lib/api"
import { formatDateTime, shortId } from "@/lib/format"

const ROLES = ["submitter", "approver", "admin"] as const

function errorMessage(err: unknown): string {
  return err instanceof ApiError ? err.message : "Request failed"
}

export function AdminPage() {
  return (
    <>
      <PageHeader
        title="Admin"
        description="Failed pipeline runs and user accounts."
      />
      <Tabs defaultValue="dlq" className="gap-6">
        <TabsList>
          <TabsTrigger value="dlq">Dead letters</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
        </TabsList>
        <TabsContent value="dlq">
          <DlqCard />
        </TabsContent>
        <TabsContent value="users">
          <UsersCard />
        </TabsContent>
      </Tabs>
    </>
  )
}

function DlqCard() {
  const queryClient = useQueryClient()
  const { data: entries, isPending } = useQuery({
    queryKey: ["dlq"],
    queryFn: api.listDlq,
  })

  const requeueMutation = useMutation({
    mutationFn: (caseId: string) => api.requeueDlq(caseId),
    onSuccess: (res) => {
      toast.success(`Case #${shortId(res.case_id)} requeued`)
      queryClient.invalidateQueries({ queryKey: ["dlq"] })
    },
    onError: (err) => toast.error(errorMessage(err)),
  })

  return (
    <Card className="py-0">
      <CardContent className="px-0">
        {isPending ? (
          <div className="flex flex-col gap-3 p-6">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-2/3" />
          </div>
        ) : !entries || entries.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <InboxIcon />
              </EmptyMedia>
              <EmptyTitle>Dead-letter queue is empty</EmptyTitle>
              <EmptyDescription>
                Cases land here only after the pipeline exhausts its retries.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="ps-6">Case</TableHead>
                <TableHead>Error</TableHead>
                <TableHead>Failed at</TableHead>
                <TableHead className="w-28" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry) => (
                <TableRow key={entry.case_id} className="hover:bg-transparent">
                  <TableCell className="ps-6 font-mono text-xs">
                    <Link
                      to={`/cases/${entry.case_id}`}
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      {shortId(entry.case_id)}
                    </Link>
                  </TableCell>
                  <TableCell
                    className="max-w-md truncate text-muted-foreground"
                    title={entry.traceback}
                  >
                    {entry.error}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(entry.failed_at)}
                  </TableCell>
                  <TableCell className="pe-4 text-end">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={requeueMutation.isPending}
                      onClick={() => requeueMutation.mutate(entry.case_id)}
                    >
                      {requeueMutation.isPending &&
                      requeueMutation.variables === entry.case_id ? (
                        <Spinner data-icon="inline-start" />
                      ) : (
                        <RotateCcwIcon data-icon="inline-start" />
                      )}
                      Requeue
                    </Button>
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

function UsersCard() {
  const queryClient = useQueryClient()
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me })
  const { data: users, isPending } = useQuery({
    queryKey: ["users"],
    queryFn: api.listUsers,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["users"] })

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      api.updateUserRole(id, role),
    onSuccess: (updated) => {
      toast.success(`${updated.email} is now ${updated.role}`)
      invalidate()
    },
    onError: (err) => {
      toast.error(errorMessage(err))
      invalidate()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => {
      toast.success("User removed")
      invalidate()
    },
    onError: (err) => toast.error(errorMessage(err)),
  })

  return (
    <div className="flex flex-col gap-6">
      <AddUserForm onCreated={invalidate} />
      <Card className="py-0">
        <CardContent className="px-0">
          {isPending ? (
            <div className="flex flex-col gap-3 p-6">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-2/3" />
            </div>
          ) : !users || users.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <UsersIcon />
                </EmptyMedia>
                <EmptyTitle>No users</EmptyTitle>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="ps-6">Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => {
                  const isSelf = u.email === me?.email
                  return (
                    <TableRow key={u.id} className="hover:bg-transparent">
                      <TableCell className="ps-6 font-medium">
                        {u.email}
                        {isSelf && (
                          <Badge variant="secondary" className="ms-2">
                            you
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Select
                          value={u.role}
                          onValueChange={(role) =>
                            roleMutation.mutate({
                              id: u.id,
                              role: String(role),
                            })
                          }
                          disabled={isSelf || roleMutation.isPending}
                        >
                          <SelectTrigger
                            size="sm"
                            aria-label={`Role for ${u.email}`}
                            className="capitalize"
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              {ROLES.map((role) => (
                                <SelectItem
                                  key={role}
                                  value={role}
                                  className="capitalize"
                                >
                                  {role}
                                </SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDateTime(u.created_at)}
                      </TableCell>
                      <TableCell className="pe-4">
                        <DeleteUserButton
                          user={u}
                          disabled={isSelf || deleteMutation.isPending}
                          onConfirm={() => deleteMutation.mutate(u.id)}
                        />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function AddUserForm({ onCreated }: { onCreated: () => void }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState<string>("approver")

  const createMutation = useMutation({
    mutationFn: () => api.createUser({ email, password, role }),
    onSuccess: (created) => {
      toast.success(`${created.email} added as ${created.role}`)
      setEmail("")
      setPassword("")
      onCreated()
    },
    onError: (err) => toast.error(errorMessage(err)),
  })

  return (
    <Card>
      <CardContent>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            createMutation.mutate()
          }}
        >
          <FieldGroup className="sm:flex-row sm:items-end">
            <Field>
              <FieldLabel htmlFor="new-email">Email</FieldLabel>
              <Input
                id="new-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@insurer.com"
                required
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="new-password">Password</FieldLabel>
              <Input
                id="new-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                minLength={4}
                required
              />
            </Field>
            <Field className="sm:w-40">
              <FieldLabel htmlFor="new-role">Role</FieldLabel>
              <Select value={role} onValueChange={(v) => setRole(String(v))}>
                <SelectTrigger
                  id="new-role"
                  className="w-full capitalize"
                  aria-label="Role"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {ROLES.map((r) => (
                      <SelectItem key={r} value={r} className="capitalize">
                        {r}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Button
              type="submit"
              disabled={createMutation.isPending}
              className="sm:shrink-0"
            >
              {createMutation.isPending ? (
                <Spinner data-icon="inline-start" />
              ) : (
                <PlusIcon data-icon="inline-start" />
              )}
              Add user
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}

function DeleteUserButton({
  user,
  disabled,
  onConfirm,
}: {
  user: AdminUser
  disabled: boolean
  onConfirm: () => void
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Delete ${user.email}`}
            className="text-destructive hover:text-destructive"
            disabled={disabled}
          >
            <Trash2Icon />
          </Button>
        }
      />
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove {user.email}?</AlertDialogTitle>
          <AlertDialogDescription>
            They lose access immediately. Audit history keeps their past
            actions.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Remove</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
