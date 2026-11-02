#!/usr/bin/env python3
"""Summarize a lens-model A/B: findings recall per lens, per model, from `claude plugin eval --json`.

evals/lens-ab/run.sh writes one report per model, named <model>.json. Each lens-ab case has graders
named after the lens that should catch the planted defect: `reviewer-…`, `sentinel-…`,
`simplifier-…`, `verifier-…`. Recall for a lens is the share of graded runs in which its graders
passed. Graders with other names (the dialect checks) are reported as `other`.

Report shape read (Claude Code 2.1.3xx `--json`):
  {"cases": [{"name": "...", "runs": [{"score": 1.0, "cost_usd": 0.4, "error": null,
               "graders": [{"name": "simplifier-finds-needless-factory", "passed": true,
                            "scored": true}]}]}]}
A run with an `error` and no graders counts as an errored run, not as a miss.

Usage: summarize.py <model>.json [<model>.json ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LENSES = ("reviewer", "sentinel", "simplifier", "verifier")


def lens_of(grader_name: str) -> str:
    head = grader_name.split("-", 1)[0]
    return head if head in LENSES else "other"


def summarize(reports: dict[str, dict]) -> dict:
    """{label: report} -> {"models": [...], "lenses": {lens: {label: [passed, total]}},
    "errored": {label: n}, "cost": {label: usd}, "cases": {label: {case: score}}}."""
    out = {"models": list(reports), "lenses": {}, "errored": {}, "cost": {}, "cases": {}}
    for label, doc in reports.items():
        errored, cost, scores = 0, 0.0, {}
        for case in (doc or {}).get("cases") or []:
            if not isinstance(case, dict):
                continue
            runs = case.get("runs") or []
            if isinstance(case.get("score"), (int, float)):
                scores[case.get("name", "?")] = float(case["score"])
            for run in runs:
                if not isinstance(run, dict):
                    continue
                cost += float(run.get("cost_usd") or 0.0)
                graders = run.get("graders") or []
                if run.get("error") and not graders:
                    errored += 1
                    continue
                for g in graders:
                    if not isinstance(g, dict) or g.get("scored") is False:
                        continue
                    cell = out["lenses"].setdefault(lens_of(str(g.get("name", ""))), {}).setdefault(label, [0, 0])
                    cell[1] += 1
                    if g.get("passed"):
                        cell[0] += 1
        out["errored"][label], out["cost"][label], out["cases"][label] = errored, cost, scores
    return out


def recall(cell) -> float | None:
    if not cell or not cell[1]:
        return None
    return cell[0] / cell[1]


def render(summary: dict) -> str:
    models = summary["models"]
    lines = ["lens        " + "".join("%-18s" % m for m in models)]
    order = [l for l in LENSES if l in summary["lenses"]] + (["other"] if "other" in summary["lenses"] else [])
    for lens in order:
        row = "%-12s" % lens
        for m in models:
            cell = summary["lenses"][lens].get(m)
            r = recall(cell)
            row += "%-18s" % ("-" if r is None else "%d/%d (%.0f%%)" % (cell[0], cell[1], 100 * r))
        lines.append(row)
    lines.append("cost (USD)  " + "".join("%-18s" % ("%.2f" % summary["cost"][m]) for m in models))
    lines.append("errored     " + "".join("%-18s" % summary["errored"][m] for m in models))
    if len(models) == 2:
        a, b = models
        for lens in order:
            ra, rb = recall(summary["lenses"][lens].get(a)), recall(summary["lenses"][lens].get(b))
            if ra is not None and rb is not None:
                lines.append("%s: %s minus %s = %+.0f points" % (lens, a, b, 100 * (ra - rb)))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    reports = {}
    for arg in argv:
        path = Path(arg)
        try:
            reports[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("cannot read %s: %s" % (arg, exc), file=sys.stderr)
            return 2
    print(render(summarize(reports)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
