export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-2xl bg-line/80 ${className}`} />
}

export function ArticleSkeleton() {
  return (
    <div className="grid gap-3">
      <Skeleton className="h-44" />
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-4/5" />
    </div>
  )
}
