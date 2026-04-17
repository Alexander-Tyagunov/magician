Common AI mistakes: SQL injection via string concatenation; XSS via innerHTML with user content; SSRF by fetching user-provided URLs without validation; storing passwords in plaintext.
Checklist: parameterize all queries; escape all output; validate/allowlist URLs; hash passwords with bcrypt/argon2; set Content-Security-Policy; use HTTPS only.
Gotchas: auth !== authz; JWTs are not encrypted by default; CORS misconfiguration allows cross-origin reads; rate-limit all auth endpoints.
