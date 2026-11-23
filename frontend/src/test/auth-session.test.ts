import { AxiosError, type InternalAxiosRequestConfig } from "axios"
import axios from "axios"
import { afterEach, describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { applyAccessSession, getAccessToken, publishAuth } from "@/lib/session"
import type { UserPublic } from "@/types/api"

const user = {
  id: "1",
  username: "ada",
  email: "ada@example.com",
  full_name: null,
  avatar_url: null,
  bio: null,
  role: "reader",
  is_active: true,
  is_verified: false,
  created_at: "",
  updated_at: "",
  last_login_at: null,
} satisfies UserPublic

function unauthorized(config: InternalAxiosRequestConfig) {
  const error = new AxiosError("unauthorized")
  error.config = config
  error.response = {
    status: 401,
    data: { error: { code: "unauthorized", message: "Authentication is required." } },
    headers: {},
    config,
    statusText: "Unauthorized",
  }
  return error
}

afterEach(() => {
  publishAuth(null)
  vi.restoreAllMocks()
  api.defaults.adapter = undefined
})

describe("refresh session", () => {
  it("shares one refresh across overlapping calls", async () => {
    let calls = 0
    vi.spyOn(axios, "post").mockImplementation(async () => {
      calls += 1
      await new Promise((resolve) => setTimeout(resolve, 15))
      return {
        data: {
          access_token: "rotated",
          token_type: "bearer",
          expires_in: 900,
          refresh_token: "must-not-be-stored",
          user,
        },
      }
    })
    const { refreshSession } = await import("@/lib/api")
    const [first, second] = await Promise.all([refreshSession(), refreshSession()])
    expect(calls).toBe(1)
    expect(first?.access_token).toBe("rotated")
    expect(second?.access_token).toBe("rotated")
    expect(localStorage.getItem("refresh_token")).toBeNull()
    expect(getAccessToken()).toBe("rotated")
  })

  it("clears the memory session when refresh fails", async () => {
    applyAccessSession("stale", user)
    vi.spyOn(axios, "post").mockRejectedValue(new Error("rejected"))
    const { refreshSession } = await import("@/lib/api")
    await expect(refreshSession()).resolves.toBeNull()
    expect(getAccessToken()).toBeNull()
  })

  it("retries one unauthorized request after a single refresh", async () => {
    applyAccessSession("stale", user)
    let refreshes = 0
    vi.spyOn(axios, "post").mockImplementation(async () => {
      refreshes += 1
      return {
        data: {
          access_token: "fresh",
          token_type: "bearer",
          expires_in: 900,
          refresh_token: "cookie-only",
          user,
        },
      }
    })
    api.defaults.adapter = async (config) => {
      const header = config.headers.get("Authorization")
      if (header !== "Bearer fresh") throw unauthorized(config)
      return { data: { ok: true }, status: 200, statusText: "OK", headers: {}, config }
    }
    const [first, second] = await Promise.all([api.get("/posts"), api.get("/categories")])
    expect(refreshes).toBe(1)
    expect(first.data).toEqual({ ok: true })
    expect(second.data).toEqual({ ok: true })
    expect(getAccessToken()).toBe("fresh")
  })
})
