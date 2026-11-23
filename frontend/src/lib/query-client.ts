import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        const status = (error as { status?: number }).status
        if (status && status >= 400 && status < 500) return false
        return failureCount < 1
      },
      refetchOnWindowFocus: false,
      staleTime: 20_000,
    },
  },
})
