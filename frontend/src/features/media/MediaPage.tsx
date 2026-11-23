import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/Button"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Input } from "@/components/ui/Input"
import { preferredVariant } from "@/lib/media-url"
import { toApiError } from "@/lib/errors"
import { deleteMedia, myMedia, updateMedia, uploadMedia } from "@/services/media"

export function MediaPage() {
  const queryClient = useQueryClient()
  const [progress, setProgress] = useState<number | null>(null)
  const query = useQuery({ queryKey: ["media", "mine"], queryFn: () => myMedia(1) })
  const upload = useMutation({
    mutationFn: (file: File) => uploadMedia(file, {}, setProgress),
    onSuccess: () => {
      setProgress(null)
      toast.success("Image stored.")
      void queryClient.invalidateQueries({ queryKey: ["media"] })
    },
    onError: (error) => {
      setProgress(null)
      toast.error(toApiError(error).message)
    },
  })
  return (
    <div>
      <h2 className="font-display text-4xl">Media</h2>
      <p className="mt-2 text-sm text-ink-soft">Uploads require an author or administrator role. Images attached to an article cannot be deleted until they are detached.</p>
      <input className="mt-4" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => {
        const file = event.target.files?.[0]
        if (file) upload.mutate(file)
      }} />
      {progress !== null ? <p className="mt-2 text-sm">Uploading {Math.round(progress * 100)}%</p> : null}
      {query.error ? <ErrorState error={query.error} /> : null}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {query.data?.items.map((item) => (
          <article key={item.id} className="rounded-3xl border border-line p-3">
            <img src={preferredVariant(item.variants, ["medium", "thumbnail"]) || ""} alt={item.alt_text || ""} className="h-40 w-full rounded-2xl object-cover" />
            <p className="mt-2 text-sm">{item.title || item.original_filename}</p>
            <p className="text-xs text-ink-soft">{item.status} · {item.mime_type}</p>
            <Input className="mt-2" defaultValue={item.alt_text ?? ""} aria-label="Alt text" onBlur={(event) => {
              updateMedia(item.id, { alt_text: event.target.value || null }).catch((error: unknown) => toast.error(toApiError(error).message))
            }} />
            <Button className="mt-2" size="sm" variant="danger" onClick={() => deleteMedia(item.id).then(() => query.refetch()).catch((error: unknown) => toast.error(toApiError(error).message))}>Delete</Button>
          </article>
        ))}
      </div>
      {query.data && query.data.items.length === 0 ? <EmptyState title="No images" body="Upload a JPEG, PNG, or WebP image." /> : null}
    </div>
  )
}
