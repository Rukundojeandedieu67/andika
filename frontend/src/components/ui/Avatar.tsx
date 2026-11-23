export function Avatar({
  name,
  src,
  size = 40,
}: {
  name: string
  src?: string | null
  size?: number
}) {
  const initial = name.trim().charAt(0).toUpperCase() || "A"
  if (src) {
    return (
      <img
        src={src}
        alt=""
        width={size}
        height={size}
        className="rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    )
  }
  return (
    <span
      aria-hidden="true"
      className="grid place-items-center rounded-full bg-brand text-sm font-semibold text-paper-raised"
      style={{ width: size, height: size }}
    >
      {initial}
    </span>
  )
}
