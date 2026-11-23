import { useEffect, useState, type ReactNode } from "react"
import { ThemeContext, type Theme } from "@/app/providers/theme-context"

const KEY = "andika_theme"

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(KEY)
    if (stored === "light" || stored === "dark") return stored
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  })

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
    localStorage.setItem(KEY, theme)
  }, [theme])

  return (
    <ThemeContext.Provider
      value={{ theme, toggle: () => setTheme((current) => (current === "dark" ? "light" : "dark")) }}
    >
      {children}
    </ThemeContext.Provider>
  )
}
