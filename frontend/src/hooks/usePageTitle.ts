import { useEffect } from "react"

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = title === "ANDIKA" ? title : `${title} · ANDIKA`
    return () => {
      document.title = "ANDIKA"
    }
  }, [title])
}
