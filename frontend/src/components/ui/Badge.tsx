export function Badge({
  children,
  tone = "neutral",
}: {
  children: string
  tone?: "neutral" | "brand" | "accent" | "danger"
}) {
  const tones = {
    neutral: "bg-line text-ink",
    brand: "bg-brand/15 text-brand-strong",
    accent: "bg-accent/15 text-accent",
    danger: "bg-danger/15 text-danger",
  }
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  )
}
