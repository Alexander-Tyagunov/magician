# Logging (principles) — Security and PII

Aligns to OpenTelemetry logs + 12-factor. OTel has **no built-in PII/secret protection** — redact at emit, then defense-in-depth (emit→collector→store→access); can't un-leak stored data.

## Never log (OWASP)
- **Secrets:** passwords, access/refresh/session tokens, API keys, private keys, DB connection strings.
- **Regulated data:** full PAN/card & bank numbers (PCI); government IDs (SSN, passport); health (PHI); biometrics.
- **Mask/pseudonymize:** email, phone, name, IP/MAC, file paths, internal hostnames.
- **Reference, not value:** `user_id`/keyed hash not email; card `last4` not PAN; token *fingerprint* (HMAC) not the token.

## Emit safely
- **Allow-list beats deny-list** — log only known-safe fields; a blocklist misses the next new field. `redaction` fails closed: empty `allowed_keys` drops every attribute.
- **Structured (JSON)** redacts by *key*; regex over free text is fragile and leaks.
- **Pseudonymize (HMAC + secret):** plain `md5`/`sha1` of low-entropy PII is reversible by lookup; HMAC correlates a subject without exposing identity.
- **Never** put PII/secrets in the message, span names, URLs/query strings, or **metric labels**.

## Pipeline redaction (each platform's own language)
- **OTel `redactionprocessor`:** `allowed_keys` (retained); `blocked_values` (regex → asterisks, or hashed via `hash_function` e.g. `hmac-sha256` + `hmac_key`); `allowed_values` beats blocked. Unlisted keys dropped first.
- **AWS CloudWatch data protection policy:** managed data identifiers (Credentials/Financial/PII/PHI/Device) + custom; masked at **all egress** (Logs Insights, metric filters); only `logs:Unmask` IAM views. Masks only data ingested **after** it's set.
- **Azure Monitor DCR transformation (KQL):** drop `source | project-away ClientIP`; obfuscate `source | extend Email = replace(Email, substring(Email,0,indexof(Email,"@")), "*****")`; or route sensitive rows to an RBAC-restricted table.
- **GCP, Grafana/Loki, Splunk, Dynatrace:** redact at the agent/collector; see each platform's lore.

## Injection & integrity (CWE-117)
- **Sanitize untrusted values** — strip/encode CR/LF so an attacker can't forge log lines; JSON encoding neutralizes this. Validate cross-trust-zone input.
- **Protect logs:** TLS in transit, least-privilege + audited *read* access, tamper detection, write-only DB sink.

## Compliance & retention
- **Classify, minimize, expire:** never log data above the store's clearance; PII must be GDPR-deletable — set short retention TTLs; honor opt-out.

## DON'T
- Rely solely on downstream masking.
- Log full request/response bodies or `Authorization`/`Cookie`/`Set-Cookie` headers verbatim.
- Emit stack traces/exception attrs unscrubbed — they capture locals, args, SQL (lore/logging/errors-and-exceptions.md).
- Leave DEBUG on in prod (lore/logging/levels-and-environments.md); or disable TLS to the backend.

## Sources
- cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- opentelemetry.io/docs/specs/otel/logs/data-model · collector-contrib redactionprocessor
- docs.aws.amazon.com/AmazonCloudWatch/latest/logs/mask-sensitive-log-data.html
- learn.microsoft.com/azure/azure-monitor/data-collection/data-collection-transformations-kql
