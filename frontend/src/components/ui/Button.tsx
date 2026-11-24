import type { ButtonHTMLAttributes } from "react"

const variants = {
  primary: "bg-accent text-white hover:brightness-95",
  secondary: "border border-line bg-paper-raised text-ink hover:border-brand",
  ghost: "text-ink hover:bg-line/60",
  danger: "bg-danger text-white hover:opacity-90",
} as const

const sizes = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-4",
  lg: "h-12 px-5 text-lg",
} as const

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants
  size?: keyof typeof sizes
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-full font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    />
  )
}
