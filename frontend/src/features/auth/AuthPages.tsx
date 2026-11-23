import { useState, type FormEvent, type ReactNode } from "react"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router"
import { toast } from "sonner"
import { Button } from "@/components/ui/Button"
import { Field } from "@/components/ui/Field"
import { Input } from "@/components/ui/Input"
import { useAuth } from "@/hooks/useAuth"
import { usePageTitle } from "@/hooks/usePageTitle"
import { toApiError } from "@/lib/errors"
import { clearHash, hashParam } from "@/lib/links"
import { passwordError, usernameError } from "@/lib/password"
import { forgotPassword, registerAccount, resendVerification, resetPassword, verifyEmail } from "@/services/auth"
import { acceptInvitation } from "@/services/publications"

function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  usePageTitle(title)
  return (
    <main className="mx-auto grid min-h-[70vh] max-w-md place-items-center px-4 py-12">
      <div className="w-full">
        <p className="text-sm tracking-[0.2em] text-accent uppercase">ANDIKA</p>
        <h1 className="mt-2 font-display text-4xl">{title}</h1>
        <div className="mt-6">{children}</div>
      </div>
    </main>
  )
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const requested = params.get("next") || (location.state as { from?: string } | null)?.from || "/"
  const from = requested.startsWith("/") && !requested.startsWith("//") ? requested : "/"
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  async function submit(event: FormEvent) {
    event.preventDefault()
    setError("")
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (caught) {
      setError(toApiError(caught).message)
    }
  }
  return (
    <AuthShell title="Sign in">
      <form className="grid gap-4" onSubmit={submit}>
        <Field label="Email" htmlFor="email"><Input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></Field>
        <Field label="Password" htmlFor="password"><Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></Field>
        {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
        <Button type="submit">Sign in</Button>
      </form>
      <p className="mt-4 text-sm"><Link to="/forgot-password">Forgot password</Link> · <Link to="/register">Create an account</Link></p>
    </AuthShell>
  )
}

export function RegisterPage() {
  const [form, setForm] = useState({ username: "", email: "", full_name: "", password: "", password_confirm: "" })
  const [error, setError] = useState("")
  const [done, setDone] = useState(false)
  function set(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }))
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    const username = usernameError(form.username)
    const password = passwordError(form.password, { username: form.username, email: form.email })
    if (username || password) {
      setError(username || password || "")
      return
    }
    if (form.password !== form.password_confirm) {
      setError("Password confirmation does not match.")
      return
    }
    try {
      await registerAccount({
        username: form.username,
        email: form.email,
        password: form.password,
        password_confirm: form.password_confirm,
        full_name: form.full_name || null,
      })
      setDone(true)
    } catch (caught) {
      setError(toApiError(caught).message)
    }
  }
  if (done) {
    return (
      <AuthShell title="Check your email">
        <p>The account is a reader. Author and administrator roles cannot be chosen during registration.</p>
        <p className="mt-3 text-sm text-ink-soft">If email delivery is not configured, the API records that without claiming a message was sent. In development the message is written on the server.</p>
        <Link to="/login" className="mt-4 inline-block text-brand">Sign in</Link>
      </AuthShell>
    )
  }
  return (
    <AuthShell title="Register">
      <form className="grid gap-4" onSubmit={submit}>
        <Field label="Username" htmlFor="username"><Input id="username" required value={form.username} onChange={(event) => set("username", event.target.value)} /></Field>
        <Field label="Email" htmlFor="email"><Input id="email" type="email" required value={form.email} onChange={(event) => set("email", event.target.value)} /></Field>
        <Field label="Full name" htmlFor="name"><Input id="name" value={form.full_name} onChange={(event) => set("full_name", event.target.value)} /></Field>
        <Field label="Password" htmlFor="password" hint="At least 12 characters, with a letter and a number."><Input id="password" type="password" required value={form.password} onChange={(event) => set("password", event.target.value)} /></Field>
        <Field label="Confirm password" htmlFor="confirm"><Input id="confirm" type="password" required value={form.password_confirm} onChange={(event) => set("password_confirm", event.target.value)} /></Field>
        {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
        <Button type="submit">Create reader account</Button>
      </form>
    </AuthShell>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [message, setMessage] = useState("")
  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      const result = await forgotPassword(email)
      setMessage(result.message)
    } catch (caught) {
      toast.error(toApiError(caught).message)
    }
  }
  return (
    <AuthShell title="Reset password">
      <form className="grid gap-4" onSubmit={submit}>
        <Field label="Email" htmlFor="email"><Input id="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></Field>
        <Button type="submit">Request reset</Button>
      </form>
      {message ? <p className="mt-4 text-sm">{message}</p> : null}
    </AuthShell>
  )
}

export function ResetPasswordPage() {
  const token = hashParam("token") || ""
  const [password, setPassword] = useState("")
  const [message, setMessage] = useState("")
  async function submit(event: FormEvent) {
    event.preventDefault()
    const problem = passwordError(password)
    if (problem) {
      toast.error(problem)
      return
    }
    try {
      const result = await resetPassword(token, password)
      clearHash()
      setMessage(result.message)
    } catch (caught) {
      toast.error(toApiError(caught).message)
    }
  }
  return (
    <AuthShell title="Choose a new password">
      {!token ? <p>Open the reset link from your email. The token stays in the address fragment and is not sent as a query parameter.</p> : null}
      <form className="grid gap-4" onSubmit={submit}>
        <Field label="New password" htmlFor="password"><Input id="password" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} /></Field>
        <Button type="submit" disabled={!token}>Update password</Button>
      </form>
      {message ? <p className="mt-4">{message} <Link to="/login">Sign in</Link></p> : null}
    </AuthShell>
  )
}

export function VerifyEmailPage() {
  const [message, setMessage] = useState("")
  const [email, setEmail] = useState("")
  async function verify(event: FormEvent) {
    event.preventDefault()
    const token = hashParam("token")
    if (!token) {
      toast.error("The verification link is missing its token.")
      return
    }
    try {
      const user = await verifyEmail(token)
      clearHash()
      setMessage(`${user.email} is verified.`)
    } catch (caught) {
      toast.error(toApiError(caught).message)
    }
  }
  async function resend(event: FormEvent) {
    event.preventDefault()
    try {
      const result = await resendVerification(email)
      toast.success(result.message)
    } catch (caught) {
      toast.error(toApiError(caught).message)
    }
  }
  return (
    <AuthShell title="Verify email">
      <form className="grid gap-4" onSubmit={verify}>
        <Button type="submit">Verify this link</Button>
      </form>
      {message ? <p className="mt-4">{message}</p> : null}
      <form className="mt-8 grid gap-3" onSubmit={resend}>
        <Field label="Resend to" htmlFor="email"><Input id="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></Field>
        <Button type="submit" variant="secondary">Resend verification</Button>
      </form>
    </AuthShell>
  )
}

export function AcceptInvitationPage() {
  const { status } = useAuth()
  const [message, setMessage] = useState("")
  async function submit(event: FormEvent) {
    event.preventDefault()
    const token = hashParam("token")
    if (!token) {
      toast.error("The invitation link is missing its token.")
      return
    }
    try {
      const member = await acceptInvitation(token)
      clearHash()
      setMessage(`You joined as ${member.role}.`)
    } catch (caught) {
      toast.error(toApiError(caught).message)
    }
  }
  if (status !== "authenticated") {
    return <AuthShell title="Accept invitation"><p>Sign in with the verified account that matches the invitation email, then return to this link.</p><Link to="/login" state={{ from: "/invitations/accept" }} className="text-brand">Sign in</Link></AuthShell>
  }
  return (
    <AuthShell title="Accept invitation">
      <form onSubmit={submit}><Button type="submit">Accept invitation</Button></form>
      {message ? <p className="mt-4">{message}</p> : null}
    </AuthShell>
  )
}
