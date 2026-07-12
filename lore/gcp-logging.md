# Google Cloud Logging — core digest
Logs Explorer "Logging query language" (a filter language, not SQL). Severity: DEBUG<INFO<NOTICE<WARNING<ERROR<CRITICAL<ALERT<EMERGENCY. JSON → jsonPayload; text → textPayload.

DO write one JSON line per event to stdout/stderr — Cloud Run/GKE/Functions parse it into jsonPayload.
DO set level via top-level "severity" (a LogSeverity string), never a message prefix.
DO correlate: emit "logging.googleapis.com/trace" (+ /spanId) so entries group by request.
DO query exact ops: `resource.type="cloud_run_revision" AND severity>=ERROR`; `=` `!=` `>=` `:`(has/substring) `=~` `!~`(RE2 regex).
DO find errors: `severity>=ERROR AND jsonPayload.message=~"timeout"`; capitalize AND/OR/NOT (`-`=NOT).
DO prefer `SEARCH(textPayload,"pool exhausted")` (token search) over bare `"..."` global search (slow).
DO promote recurring queries to log-based metrics (counter/distribution) + alert.

DON'T hardcode DEBUG in prod — gate by env (INFO/WARN prod, DEBUG dev).
DON'T log secrets/PII/tokens; jsonPayload is indexed + queryable.
DON'T lowercase and/or/not — they parse as search terms.
DON'T set level from `message`; only top-level `severity` controls it.

Deep dive when writing non-trivial Google Cloud Logging — read lore/gcp-logging/{logging-query-language,structured-logging-and-severity,sinks-metrics-and-alerts}.md

## Sources
docs.cloud.google.com/logging/docs/view/logging-query-language · /structured-logging · /logs-based-metrics
