import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/Button"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Input } from "@/components/ui/Input"
import { Skeleton } from "@/components/ui/Skeleton"
import { mediaFileError } from "@/features/editor/article-desk"
import { usePageTitle } from "@/hooks/usePageTitle"
import { toApiError } from "@/lib/errors"
import { preferredVariant } from "@/lib/media-url"
import { deleteMedia, myMedia, updateMedia, uploadMedia } from "@/services/media"

const kinds = [
  { id: "all", label: "All Types" },
  { id: "jpeg", label: "JPEG" },
  { id: "png", label: "PNG" },
  { id: "webp", label: "WebP" },
] as const

export function MediaPage() {
  usePageTitle("Media Library")
  const queryClient = useQueryClient()
  const [progress, setProgress] = useState<number | null>(null)
  const [search, setSearch] = useState("")
  const [kind, setKind] = useState<(typeof kinds)[number]["id"]>("all")
  const query = useQuery({ queryKey: ["media", "mine", search], queryFn: () => myMedia(1, search) })
  const items = (query.data?.items ?? []).filter((item) => kind === "all" || item.mime_type.includes(kind))
  const upload = useMutation({
    mutationFn: (file: File) => uploadMedia(file, {}, setProgress),
    onSuccess: () => {
      setProgress(null)
      toast.success("Image stored in your library. It is not attached to an article until you save that choice.")
      void queryClient.invalidateQueries({ queryKey: ["media"] })
    },
    onError: (error) => {
      setProgress(null)
      toast.error(toApiError(error).message)
    },
  })
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-4xl">Media Library</h2>
          <p className="mt-2 max-w-2xl text-sm text-ink-soft">Verified authors and administrators can upload JPEG, PNG, and WebP images up to 10 MB. An upload stays in this library until an article saves it as the featured image.</p>
        </div>
        <label className="inline-flex h-11 cursor-pointer items-center rounded-full bg-forest px-4 text-sm text-white">
          Upload Media
          <input className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" aria-label="Upload image" onChange={(event) => {
        const file = event.target.files?.[0]
        event.currentTarget.value = ""
        if (!file) return
        const problem = mediaFileError(file)
        if (problem) {
          toast.error(problem)
          return
        }
        upload.mutate(file)
      }} />
        </label>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search media..." aria-label="Search media" className="max-w-sm" />
        <div className="flex gap-2" role="group" aria-label="File type">
          {kinds.map((item) => (
            <button key={item.id} type="button" className={`rounded-full px-3 py-2 text-sm ${kind === item.id ? "bg-forest text-white" : "border border-line"}`} onClick={() => setKind(item.id)}>{item.label}</button>
          ))}
        </div>
      </div>
      {progress !== null ? <p className="mt-2 text-sm" role="status">Uploading {Math.round(progress * 100)}%</p> : null}
      {query.isLoading ? <Skeleton className="mt-6 h-40" /> : null}
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <article key={item.id} className="overflow-hidden rounded-3xl border border-line bg-paper-raised">
            <img src={preferredVariant(item.variants, ["medium", "thumbnail"]) || ""} alt={item.alt_text || item.title || "Uploaded image"} className="h-44 w-full object-cover" />
            <div className="p-3">
            <p className="text-sm">{item.title || item.original_filename}</p>
            <p className="text-xs text-ink-soft">{item.mime_type}</p>
            <Input className="mt-2" defaultValue={item.alt_text ?? ""} aria-label={`Alt text for ${item.title || item.original_filename}`} onBlur={(event) => {
              updateMedia(item.id, { alt_text: event.target.value || null }).then(() => toast.success("Alt text saved.")).catch((error: unknown) => toast.error(toApiError(error).message))
            }} />
            <Button className="mt-2" size="sm" variant="danger" onClick={() => {
              if (!window.confirm("Delete this image from your library?")) return
              deleteMedia(item.id).then(() => query.refetch()).catch((error: unknown) => toast.error(toApiError(error).message))
            }}>Delete</Button>
            </div>
          </article>
        ))}
      </div>
      {query.data && items.length === 0 ? <EmptyState title="No images" body="Upload a JPEG, PNG, or WebP image. It will not be attached to an article until you choose it in the editor and save." /> : null}
    </div>
  )
}
