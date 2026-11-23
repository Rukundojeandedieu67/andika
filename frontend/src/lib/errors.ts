import type { ApiErrorBody } from "@/types/api"
import axios from "axios"

export class ApiError extends Error {
  status: number
  code: string
  details: Array<{ loc: Array<string | number>; message: string }>

  constructor(
    status: number,
    code: string,
    message: string,
    details: Array<{ loc: Array<string | number>; message: string }> = [],
  ) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.details = details
  }
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? 0
    const data = error.response?.data as ApiErrorBody | undefined
    const message =
      data?.error?.message ||
      (status === 0
        ? "The ANDIKA API could not be reached."
        : "The request could not be completed.")
    return new ApiError(status, data?.error?.code || "http_error", message, data?.details ?? [])
  }
  if (error instanceof Error) return new ApiError(0, "client_error", error.message)
  return new ApiError(0, "client_error", "Something went wrong.")
}

export function fieldErrors(error: unknown): Record<string, string> {
  const apiError = toApiError(error)
  const fields: Record<string, string> = {}
  for (const detail of apiError.details) {
    const key = detail.loc.filter((part) => part !== "body").join(".")
    if (key) fields[key] = detail.message
  }
  return fields
}
