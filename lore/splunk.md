# Splunk — core digest
Splunk Enterprise 10.x / Cloud Platform: events in indexes, queried in SPL (Search Processing Language); app logs sent via HTTP Event Collector (HEC). Splunk Observability Cloud is a SEPARATE product (metrics/APM/RUM), not SPL-over-indexes.

DO ship JSON to HEC: POST `/services/collector/event` (:8088), `Authorization: Splunk <token>`, body `{"event":{...},"sourcetype":"app:json","index":"app_prod"}`.
DO route by index (retention/access) + sourcetype (parsing); set index per env, not hardcoded.
DO front a search with a tight base filter before `|`: `index=app_prod sourcetype=app:json status>=500`.
DO aggregate with stats: `index=app_prod level=ERROR | stats count by error_code`; conditional `| stats count(eval(status>=500)) AS errors by service`.
DO filter value sets with IN: `status IN (500,502,503)`.
DO trace a request by its propagated id: `index=app_prod request_id="abc-123"`.

DON'T write SQL/KQL/LogQL — SPL pipes `search | stats`; `=`/`!=` string, `<`/`>` numeric/lexical.
DON'T scan `index=*` or leave time open — bound index + earliest/latest.
DON'T send secrets/PII in events — HEC indexes them verbatim.

Deep dive when writing non-trivial Splunk — read lore/splunk/{spl-search-and-stats,ingestion-sourcetypes-indexes,dashboards-and-alerts}.md

## Sources
help.splunk.com — SearchReference/{Stats,Search}, Data/{UsetheHTTPEventCollector,FormateventsforHTTPEventCollector}, Enterprise 10.4 release notes
