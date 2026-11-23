import { apiBaseUrl } from "@/lib/config"
import { ApiError, toApiError } from "@/lib/errors"
import { applyAccessSession, getAccessToken, publishAuth } from "@/lib/session"
import type { AccessTokenResponse } from "@/types/api"
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios"

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean; _skipAuth?: boolean }

export const api = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
  headers: { Accept: "application/json" },
})

let refreshRequest: Promise<AccessTokenResponse | null> | null = null

export async function refreshSession(): Promise<AccessTokenResponse | null> {
  if (!refreshRequest) {
    refreshRequest = axios
      .post<AccessTokenResponse>(
        `${apiBaseUrl}/auth/refresh`,
        {},
        { withCredentials: true, headers: { Accept: "application/json" } },
      )
      .then((response) => {
        applyAccessSession(response.data.access_token, response.data.user)
        return response.data
      })
      .catch(() => {
        publishAuth(null)
        return null
      })
      .finally(() => {
        refreshRequest = null
      })
  }
  return refreshRequest
}

api.interceptors.request.use((config: RetryConfig) => {
  const token = getAccessToken()
  if (token && !config._skipAuth) {
    config.headers.set("Authorization", `Bearer ${token}`)
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined
    const status = error.response?.status
    const url = config?.url ?? ""
    const isAuthRoute = url.includes("/auth/refresh") || url.includes("/auth/login")
    if (status === 401 && config && !config._retry && !isAuthRoute && getAccessToken()) {
      config._retry = true
      const session = await refreshSession()
      if (session) {
        config.headers.set("Authorization", `Bearer ${session.access_token}`)
        return api.request(config)
      }
    }
    return Promise.reject(error instanceof ApiError ? error : toApiError(error))
  },
)
