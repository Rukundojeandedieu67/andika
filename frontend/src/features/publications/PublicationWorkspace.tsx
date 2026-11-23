import { useState, type FormEvent } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/Button"
import { Field } from "@/components/ui/Field"
import { Input } from "@/components/ui/Input"
import { Select } from "@/components/ui/Select"
import { Textarea } from "@/components/ui/Textarea"
import { toApiError } from "@/lib/errors"
import { formatDateTime } from "@/lib/format"
import {
  archivePublication,
  auditLogs,
  changeMemberRole,
  createPublication,
  inviteMember,
  listInvitations,
  listMembers,
  managePublication,
  myPublications,
  removeMember,
  restorePublication,
  revokeInvitation,
  suspendMember,
  transferOwnership,
  updatePublication,
} from "@/services/publications"
import { editorialPosts, editorialSubmissions } from "@/services/content"
import {
  downloadPublicationExport,
  publicationArticles,
  publicationAuthors,
  publicationOverview,
} from "@/services/analytics"
import { AnalyticsFilters, AnalyticsNotes } from "@/features/analytics/AuthorAnalyticsPage"
import type { InviteRole, MembershipRole } from "@/types/api"
import type { AnalyticsQuery } from "@/services/analytics"
import { formatNumber, formatRate } from "@/lib/format"

export function MyPublicationsPage() {
  const query = useQuery({ queryKey: ["my-publications"], queryFn: () => myPublications(1) })
  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-4xl">Publications</h2>
        <Link to="/workspace/publications/new" className="rounded-full bg-brand px-4 py-2 text-paper-raised">New publication</Link>
      </div>
      <div className="mt-6 grid gap-3">
        {query.data?.items.map((item) => (
          <Link key={item.id} to={`/workspace/publications/${item.id}`} className="rounded-2xl border border-line px-4 py-3">
            {item.name} · {item.role} · {item.visibility} · {item.status}
          </Link>
        ))}
      </div>
      {query.error ? <p className="mt-4 text-sm">{toApiError(query.error).message}</p> : null}
    </div>
  )
}

export function NewPublicationPage() {
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [visibility, setVisibility] = useState("public")
  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      const created = await createPublication({ name, description: description || null, visibility, requires_review: true })
      toast.success("Publication created. You are the owner.")
      navigate(`/workspace/publications/${created.id}`)
    } catch (error) {
      toast.error(toApiError(error).message)
    }
  }
  return (
    <form className="grid max-w-xl gap-4" onSubmit={submit}>
      <h2 className="font-display text-4xl">New publication</h2>
      <Field label="Name" htmlFor="name"><Input id="name" required value={name} onChange={(event) => setName(event.target.value)} /></Field>
      <Field label="Description" htmlFor="description"><Textarea id="description" value={description} onChange={(event) => setDescription(event.target.value)} /></Field>
      <Field label="Visibility" htmlFor="visibility">
        <Select id="visibility" value={visibility} onChange={(event) => setVisibility(event.target.value)}>
          <option value="public">Public</option>
          <option value="private">Private</option>
        </Select>
      </Field>
      <Button type="submit">Create</Button>
    </form>
  )
}

export function PublicationManagePage() {
  const { id = "" } = useParams()
  const queryClient = useQueryClient()
  const manage = useQuery({ queryKey: ["publication-manage", id], queryFn: () => managePublication(id) })
  const members = useQuery({ queryKey: ["members", id], queryFn: () => listMembers(id) })
  const invitations = useQuery({ queryKey: ["invitations", id], queryFn: () => listInvitations(id), retry: false })
  const posts = useQuery({ queryKey: ["editorial", id], queryFn: () => editorialPosts(id) })
  const submissions = useQuery({ queryKey: ["submissions", id], queryFn: () => editorialSubmissions(id), retry: false })
  const audits = useQuery({ queryKey: ["audit", id], queryFn: () => auditLogs(id), retry: false })
  const [analyticsQuery, setAnalyticsQuery] = useState<AnalyticsQuery>({ period: "day" })
  const overview = useQuery({ queryKey: ["pub-analytics", id, analyticsQuery], queryFn: () => publicationOverview(id, analyticsQuery) })
  const performance = useQuery({ queryKey: ["pub-articles", id, analyticsQuery], queryFn: () => publicationArticles(id, analyticsQuery) })
  const authors = useQuery({ queryKey: ["pub-authors", id, analyticsQuery], queryFn: () => publicationAuthors(id, analyticsQuery) })
  const publication = manage.data
  const role = publication?.caller_role
  const isOwner = role === "owner"
  const isEditor = role === "editor" || isOwner
  const [email, setEmail] = useState("")
  const [inviteRole, setInviteRole] = useState<InviteRole>("author")
  const [description, setDescription] = useState("")
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["publication-manage", id] })
  if (manage.isLoading) return <div className="h-40 animate-pulse rounded-3xl bg-line" />
  if (manage.error || !publication) return <p>{toApiError(manage.error).message}</p>
  const inviteRoles: InviteRole[] = isOwner ? ["editor", "author", "contributor"] : ["author", "contributor"]
  const canInvite = isOwner || (role === "editor" && publication.editors_can_invite)
  return (
    <div className="grid gap-8">
      <div>
        <h2 className="font-display text-4xl">{publication.name}</h2>
        <p className="text-sm text-ink-soft">{publication.caller_role} · {publication.status} · {publication.visibility} · review {publication.requires_review ? "required" : "off"}</p>
        <Link to={`/publications/${publication.slug}`} className="text-sm text-brand">Public page</Link>
      </div>
      {isEditor ? (
        <form className="grid gap-3" onSubmit={(event) => {
          event.preventDefault()
          const fields = isOwner
            ? { description: description || publication.description, requires_review: publication.requires_review }
            : { description: description || publication.description }
          updatePublication(id, fields).then(() => { toast.success("Settings saved."); refresh() }).catch((error: unknown) => toast.error(toApiError(error).message))
        }}>
          <Field label="Description" htmlFor="description"><Textarea id="description" defaultValue={publication.description ?? ""} onChange={(event) => setDescription(event.target.value)} /></Field>
          {isOwner ? (
            <label className="text-sm"><input type="checkbox" defaultChecked={publication.requires_review} onChange={(event) => updatePublication(id, { requires_review: event.target.checked }).then(refresh)} /> Require editorial review</label>
          ) : null}
          <Button type="submit">Save description</Button>
        </form>
      ) : null}
      {isOwner && publication.status === "active" ? <Button variant="secondary" onClick={() => archivePublication(id).then(refresh).catch((error: unknown) => toast.error(toApiError(error).message))}>Archive publication</Button> : null}
      {isOwner && publication.status === "archived" ? <Button onClick={() => restorePublication(id).then(refresh).catch((error: unknown) => toast.error(toApiError(error).message))}>Restore publication</Button> : null}
      <section>
        <h3 className="font-display text-2xl">Articles</h3>
        <Link to={`/workspace/articles/new?publication=${id}`} className="text-sm text-brand">Write in this publication</Link>
        <div className="mt-3 grid gap-2">
          {posts.data?.items.map((post) => (
            <Link key={post.id} to={`/workspace/articles/${post.id}?publication=${id}`} className="rounded-2xl border border-line px-3 py-2">
              {post.title} · {post.status} · {post.editorial_status}
            </Link>
          ))}
        </div>
      </section>
      {isEditor ? (
        <section>
          <h3 className="font-display text-2xl">Submissions</h3>
          {submissions.data?.items.map((post) => (
            <Link key={post.id} to={`/workspace/articles/${post.id}?publication=${id}`} className="mt-2 block">{post.title} · {post.editorial_status}</Link>
          ))}
        </section>
      ) : null}
      <section>
        <h3 className="font-display text-2xl">Members</h3>
        {members.data?.items.map((member) => (
          <div key={member.id} className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span>{member.user.username} · {member.role} · {member.status}</span>
            {isOwner && member.role !== "owner" ? (
              <>
                <Select aria-label={`Role for ${member.user.username}`} value={member.role} onChange={(event) => changeMemberRole(id, member.id, event.target.value).then(() => members.refetch()).catch((error: unknown) => toast.error(toApiError(error).message))}>
                  {(["editor", "author", "contributor"] as MembershipRole[]).map((value) => <option key={value} value={value}>{value}</option>)}
                </Select>
                {member.status === "active" ? <button type="button" onClick={() => suspendMember(id, member.id).then(() => members.refetch())}>Suspend</button> : null}
                <button type="button" onClick={() => removeMember(id, member.id).then(() => members.refetch())}>Remove</button>
                <button type="button" onClick={() => transferOwnership(id, member.user.id).then(refresh).catch((error: unknown) => toast.error(toApiError(error).message))}>Make owner</button>
              </>
            ) : null}
          </div>
        ))}
      </section>
      {canInvite ? (
        <form className="flex flex-wrap gap-2" onSubmit={(event) => {
          event.preventDefault()
          inviteMember(id, email, inviteRole).then((result) => { toast.success(result.message); setEmail(""); void invitations.refetch() }).catch((error: unknown) => toast.error(toApiError(error).message))
        }}>
          <Input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" aria-label="Invitation email" />
          <Select aria-label="Invitation role" value={inviteRole} onChange={(event) => setInviteRole(event.target.value as InviteRole)}>
            {inviteRoles.map((value) => <option key={value} value={value}>{value}</option>)}
          </Select>
          <Button type="submit">Invite</Button>
        </form>
      ) : null}
      {invitations.data?.items.map((invitation) => (
        <p key={invitation.id} className="text-sm">{invitation.email} · {invitation.role} · {invitation.status}
          {invitation.status === "pending" && (isOwner || (role === "editor" && invitation.role !== "editor")) ? (
            <button type="button" className="ml-2" onClick={() => revokeInvitation(id, invitation.id).then(() => invitations.refetch())}>Revoke</button>
          ) : null}
        </p>
      ))}
      {isEditor ? (
        <section>
          <h3 className="font-display text-2xl">Audit history</h3>
          {audits.data?.items.map((item) => (
            <p key={item.id} className="text-sm">{formatDateTime(item.created_at)} · {item.action} · {item.actor.username}</p>
          ))}
        </section>
      ) : null}
      <section>
        <h3 className="font-display text-2xl">Analytics</h3>
        <p className="text-sm text-ink-soft">Active publication authors are authors of currently published articles in this scope.</p>
        <AnalyticsFilters query={analyticsQuery} onChange={setAnalyticsQuery} />
        {overview.data ? <p className="mt-3">Scope {overview.data.scope}. Published {formatNumber(overview.data.published_articles)}. Period views {formatNumber(overview.data.period_views)}. Active authors {formatNumber(overview.data.active_authors)}.</p> : null}
        <table className="mt-3 w-full text-sm">
          <tbody>
            {performance.data?.items.map((item) => (
              <tr key={item.id}><td>{item.title}</td><td>{formatNumber(item.views)}</td><td>{formatRate(item.engagement_rate)}</td></tr>
            ))}
          </tbody>
        </table>
        {authors.data?.items.map((author) => (
          <p key={author.user_id} className="text-sm">{author.username}: {author.published_articles} articles, {author.views} views</p>
        ))}
        <Button className="mt-3" onClick={() => downloadPublicationExport(id, analyticsQuery)}>Export CSV</Button>
        <AnalyticsNotes limitations={overview.data?.limitations} />
      </section>
    </div>
  )
}
