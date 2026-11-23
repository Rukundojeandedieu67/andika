import { useState, type FormEvent } from "react"
import { toast } from "sonner"
import { useAuth } from "@/hooks/useAuth"
import { usePageTitle } from "@/hooks/usePageTitle"
import { Button } from "@/components/ui/Button"
import { Field } from "@/components/ui/Field"
import { Input } from "@/components/ui/Input"
import { Textarea } from "@/components/ui/Textarea"
import { toApiError } from "@/lib/errors"
import { usernameError } from "@/lib/password"
import { resendVerification } from "@/services/auth"

export function AccountPage() {
  usePageTitle("Account")
  const { user, saveProfile } = useAuth()
  const [username, setUsername] = useState(user?.username ?? "")
  const [fullName, setFullName] = useState(user?.full_name ?? "")
  const [bio, setBio] = useState(user?.bio ?? "")
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? "")
  if (!user) return null
  async function submit(event: FormEvent) {
    event.preventDefault()
    const problem = usernameError(username)
    if (problem) {
      toast.error(problem)
      return
    }
    try {
      await saveProfile({
        username,
        full_name: fullName || null,
        bio: bio || null,
        avatar_url: avatarUrl || null,
      })
      toast.success("Profile updated.")
    } catch (error) {
      toast.error(toApiError(error).message)
    }
  }
  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="font-display text-5xl">Profile</h1>
      <p className="mt-2 text-ink-soft">
        {user.role} · {user.is_verified ? "email verified" : "email not verified"}
      </p>
      {!user.is_verified ? (
        <button
          type="button"
          className="mt-3 text-sm text-brand"
          onClick={() =>
            resendVerification(user.email)
              .then((result) => toast.success(result.message))
              .catch((error: unknown) => toast.error(toApiError(error).message))
          }
        >
          Resend verification
        </button>
      ) : null}
      <form className="mt-8 grid gap-4" onSubmit={submit}>
        <Field label="Username" htmlFor="username">
          <Input id="username" value={username} onChange={(event) => setUsername(event.target.value)} />
        </Field>
        <Field label="Full name" htmlFor="full-name">
          <Input id="full-name" value={fullName} onChange={(event) => setFullName(event.target.value)} />
        </Field>
        <Field label="Bio" htmlFor="bio">
          <Textarea id="bio" value={bio} maxLength={1000} onChange={(event) => setBio(event.target.value)} />
        </Field>
        <Field label="Avatar URL" htmlFor="avatar" hint="An absolute http or https URL.">
          <Input id="avatar" value={avatarUrl} onChange={(event) => setAvatarUrl(event.target.value)} />
        </Field>
        <Button type="submit">Save profile</Button>
      </form>
      <p className="mt-6 text-sm text-ink-soft">
        Role, verification, and password are not changed on this form. Password resets use the email link.
      </p>
    </main>
  )
}
