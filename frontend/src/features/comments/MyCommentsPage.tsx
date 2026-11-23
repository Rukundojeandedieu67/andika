import { useQuery } from "@tanstack/react-query"
import { myComments } from "@/services/community"

export function MyCommentsPage() {
  const query = useQuery({ queryKey: ["my-comments"], queryFn: () => myComments(1) })
  return (
    <div>
      <h2 className="font-display text-4xl">My comments</h2>
      {query.data?.items.map((comment) => (
        <p key={comment.id} className="mt-3 text-sm">
          {comment.status} · {comment.body}
        </p>
      ))}
    </div>
  )
}
