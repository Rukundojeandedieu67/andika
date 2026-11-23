const COMMON_PASSWORDS = new Set([
  "password1234",
  "password12345",
  "changeme1234",
  "qwerty123456",
  "letmein12345",
  "andika123456",
  "admin1234567",
  "welcome12345",
])

export function passwordError(
  password: string,
  options: { username?: string; email?: string } = {},
): string | null {
  if (password.length < 12) return "Password must be at least 12 characters."
  if (password.length > 1024) return "Password exceeds the maximum length."
  if (password.trim() !== password || password.trim() === "") {
    return "Password must not begin or end with spaces."
  }
  if (!/[A-Za-z]/.test(password)) return "Password must include a letter."
  if (!/\d/.test(password)) return "Password must include a number."
  if (COMMON_PASSWORDS.has(password.toLowerCase())) return "Password is too common."
  const lowered = password.toLowerCase()
  if (options.username && lowered.includes(options.username.toLowerCase())) {
    return "Password must not contain the username."
  }
  const local = options.email?.split("@")[0]?.toLowerCase()
  if (local && local.length >= 4 && lowered.includes(local)) {
    return "Password must not contain the email address."
  }
  return null
}

export function usernameError(username: string): string | null {
  if (!/^[A-Za-z][A-Za-z0-9_]{2,29}$/.test(username)) {
    return "Username must be 3 to 30 characters, start with a letter, and use only letters, numbers, and underscores."
  }
  return null
}
