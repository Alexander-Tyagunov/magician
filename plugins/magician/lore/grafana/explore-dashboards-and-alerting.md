# Grafana + Loki — Explore, Dashboards, and Alerting

Grafana visualizes many sources; for LOGS the store is **Loki**, queried in **LogQL** (syntax: lore/grafana/loki-and-logql.md; index: lore/grafana/labels-and-cardinality.md). Workflow layer: **Explore** = ad-hoc, **dashboards** = curated panels, **alerting** = conditions. Traces=**Tempo**, metrics=**Mimir/Prometheus**; correlate all three in Explore. Verify against Grafana 12 / Loki 3.x docs.

## Explore — ad-hoc investigation
- DO start queryless in **Grafana Logs Drilldown** (formerly "Explore Logs"): filter by **labels, fields, or patterns** with no LogQL — it auto-generates panels, groups noisy lines into patterns, and links out to Explore.
- DO drop into **Explore** to write LogQL, use **Live** for real-time tailing, and **Show context** for ±N surrounding lines (like `grep -C`) — then **Open in split view**.
- DO click fields in **Log details** as filters — grouped as **Indexed labels**, **Parsed fields**, **Structured metadata**. Switching a metrics-source query to Loki keeps matching labels (`m{job="api"}` → `{job="api"}`).

## Dashboards — curated panels
- DO use the **Logs panel** for raw lines (log query); **Time series/Stat** panels need a **metric query** (`rate`, `count_over_time`, …).
- DO parameterize via `label_values(app)` template variables; pin a range; annotate deploys.
```logql
# Time series panel: 5xx rate per route
sum by (route) (rate({namespace="prod",app="api"} | json | status>=500 [5m]))
```

## Alerting — from a LogQL metric query
A **Grafana-managed alert rule** = one or more **queries and expressions** + an **alert condition**. A Loki logs query must reduce to a single numeric value, so chain expressions:
- **A** — metric query: `sum(rate({app="api"} |= "error" [5m]))`
- **B** — **Reduce** expression (series → one number, e.g. function **Last**) on A.
- **C** — **Threshold** expression on B (e.g. `IS ABOVE 0.5`); set **C** as the alert condition.

- Expression types: **Reduce**, **Math**, **Resample**, **Threshold**. Avoid **Classic condition (legacy)**.
- DO group by a label for one **alert instance per dimension**: `sum by (service) (rate({namespace="prod"} | json | level="error" [5m]))`.
- DO guard empty results so absent logs don't misfire: `sum(count_over_time({app="api"} |= "error" [5m])) or vector(0)` (No Data/Error are Grafana-managed only).
- DO set an **evaluation group** + **interval** and a **pending period** — the instance goes **Normal → Pending → Alerting** only if the breach persists (prevents flap on a transient spike); **keep firing for** holds it **Recovering** so brief recoveries don't re-notify.
- DO route via **contact points** + **notification policies** (label-matching tree); tune with **notification grouping**, **silences**, **mute timings**.

## DON'T
- DON'T alert on a raw log/range query — it returns a series, not a number; always Reduce → Threshold.
- DON'T set the evaluation interval below the query `[range]`, or a pending period below one interval.
- DON'T build panels over unbounded `{app=~".+"}` scans — pin real labels and a range.

## Sources
- grafana.com/docs/grafana/latest/explore/logs-integration/ (tail, context, split view, details)
- grafana.com/docs/grafana/latest/explore/simplified-exploration/logs/ (Grafana Logs Drilldown)
- grafana.com/docs/grafana/latest/alerting/fundamentals/ (+ alert-rules/queries-conditions/, alert-rule-evaluation/)
