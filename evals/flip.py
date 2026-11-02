#!/usr/bin/env python3
"""Flip-aware comparison of a `claude plugin eval --json` result with the tracked baseline.

scripts/gate.sh runs this after the eval tier. It never calls the model and never spends money.

A FLIP is a case that passed every run in the baseline (`evals/results/last.json`) and failed at
least one run now. A flip fails the tier, whatever the aggregate score says: one lost run in three
is how a real regression first shows. New cases and improved cases are reported only.

Cases tagged `expected-fail` (in prompt.md `tags:` or case.yaml `tags`) are left out of flip and
threshold checks until the baseline records them as passing every run. Then they count like any
other case, so drop the tag once that happens.

Result shapes read (the per-case shape of `--json` is not in the public docs, so this is defensive):

  A. What Claude Code 2.1.3xx writes (read from its `--json` output):
       {"cases": [{"name": "...", "score": 0.67, "pass_rate": 0.33,
                   "runs": [{"score": 1.0, "graders": [...], "error": null}, ...],
                   "runs_without": [...]}], ...}
     A run passes when its `score` is 1 (every scored grader passed) and it has no `error`.
     A run with only `passed: true|false` is read as that.
  B. A flat shape: {"results": [{"case": "...", "score": 0.67}]}. Without runs, the case passed
     every run only when `score` is 1.

Baseline shape (`evals/results/last.json`, tracked like budget.json):
  {"schema": 1, "recorded_at": "<UTC>", "cases": {"<name>": {"runs": 3, "passed": 3,
   "pass_rate": 1.0, "score": 1.0}}}

A baseline case missing from this run is reported as "missing" and fails the tier, unless the run
was filtered by tag (scripts/gate.sh --tag sets MAGICIAN_EVAL_TAG_FILTERED=1, or pass --tag-filtered):
then the cases left out are only reported.

`--update-baseline` writes last.json only from a run that passed the tier (no flip, nothing below the
threshold, nothing missing, no load error); `--force-baseline` writes it anyway. A tag-filtered run
merges its cases into the existing baseline instead of replacing it.

Usage:
  flip.py compare --results R.json --baseline last.json --evals-dir evals [--threshold 0.8]
                  [--exit-code N] [--update-baseline [--force-baseline]] [--tag-filtered]
Exit 0 when the tier passes, 1 when it fails, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

EXPECTED_FAIL = "expected-fail"


# ---- reading results ----------------------------------------------------------------------------

def _run_passed(run) -> bool:
    if not isinstance(run, dict):
        return bool(run)
    if run.get("error") or run.get("ended_on_api_error"):
        return False
    if "passed" in run and not isinstance(run.get("score"), (int, float)):
        return bool(run["passed"])
    score = run.get("score")
    if isinstance(score, (int, float)):
        return score >= 1.0 - 1e-9
    return bool(run.get("passed"))


def _summary_from_runs(runs: list) -> dict:
    n = len(runs)
    passed = sum(1 for r in runs if _run_passed(r))
    scores = [r.get("score") for r in runs if isinstance(r, dict) and isinstance(r.get("score"), (int, float))]
    score = sum(scores) / len(scores) if scores else (passed / n if n else 0.0)
    return {"runs": n, "passed": passed, "pass_rate": (passed / n) if n else 0.0, "score": score}


def parse_results(doc) -> dict[str, dict]:
    """Return {case name: {"runs", "passed", "pass_rate", "score"}} from either result shape."""
    out: dict[str, dict] = {}
    if not isinstance(doc, dict):
        raise ValueError("eval result is not a JSON object")
    if isinstance(doc.get("cases"), list):
        for case in doc["cases"]:
            if not isinstance(case, dict):
                continue
            name = case.get("name") or case.get("case")
            if not name:
                continue
            runs = case.get("runs")
            if isinstance(runs, list) and runs:
                summary = _summary_from_runs(runs)
                if isinstance(case.get("score"), (int, float)):
                    summary["score"] = float(case["score"])
            else:
                score = float(case.get("score", 0.0) or 0.0)
                rate = case.get("pass_rate")
                rate = float(rate) if isinstance(rate, (int, float)) else (1.0 if score >= 1.0 else 0.0)
                summary = {"runs": 0, "passed": 0, "pass_rate": rate, "score": score}
            out[str(name)] = summary
        return out
    if isinstance(doc.get("results"), list):
        for row in doc["results"]:
            if not isinstance(row, dict):
                continue
            name = row.get("case") or row.get("name")
            if not name:
                continue
            runs = row.get("runs")
            if isinstance(runs, list) and runs:
                summary = _summary_from_runs(runs)
            else:
                score = float(row.get("score", 0.0) or 0.0)
                summary = {"runs": 0, "passed": 0, "pass_rate": 1.0 if score >= 1.0 else 0.0, "score": score}
            out[str(name)] = summary
        return out
    raise ValueError("eval result has neither cases[] nor results[]")


def load_errors(doc) -> list[str]:
    """Load failures and runs the harness could not grade; any of them fails the tier."""
    problems: list[str] = []
    if isinstance(doc, dict):
        for err in doc.get("errors") or []:
            if isinstance(err, dict):
                problems.append("load error: %s: %s" % (err.get("file", "?"), err.get("error", "?")))
            else:
                problems.append("load error: %s" % err)
        for case in doc.get("cases") or []:
            if not isinstance(case, dict):
                continue
            for run in (case.get("runs") or []) + (case.get("runs_without") or []):
                if isinstance(run, dict) and run.get("ended_on_api_error"):
                    problems.append("API error run: %s" % case.get("name", "?"))
                    break
    return problems


def all_passed(summary: dict | None) -> bool:
    if not summary:
        return False
    if summary.get("runs"):
        return summary.get("passed") == summary.get("runs")
    return summary.get("pass_rate", 0.0) >= 1.0 - 1e-9


# ---- reading case tags --------------------------------------------------------------------------

def _tags_from_text(text: str) -> list[str]:
    m = re.search(r"^tags:\s*\[([^\]]*)\]", text, re.M)
    if not m:
        return []
    return [t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()]


def case_tags(evals_dir: Path) -> dict[str, set[str]]:
    """{case name: tags} from every prompt.md frontmatter and case.yaml (JSON) under evals_dir."""
    tags: dict[str, set[str]] = {}
    for case_dir in sorted(p for p in evals_dir.rglob("*") if p.is_dir()):
        if "results" in case_dir.relative_to(evals_dir).parts:
            continue
        prompt, yaml = case_dir / "prompt.md", case_dir / "case.yaml"
        if not prompt.exists() and not yaml.exists():
            continue
        name, found = case_dir.name, set()
        if yaml.exists():
            try:
                doc = json.loads(yaml.read_text(encoding="utf-8"))
                name = doc.get("name", name)
                found.update(doc.get("tags") or [])
            except ValueError:
                found.update(_tags_from_text(yaml.read_text(encoding="utf-8")))
        if prompt.exists():
            text = prompt.read_text(encoding="utf-8")
            fm = text.split("\n---", 1)[0] if text.startswith("---") else ""
            m = re.search(r"^name:\s*(\S+)", fm, re.M)
            if m:
                name = m.group(1).strip("'\"")
            found.update(_tags_from_text(fm))
        tags[name] = found
    return tags


# ---- comparing ----------------------------------------------------------------------------------

def compare(baseline: dict[str, dict], current: dict[str, dict], tags: dict[str, set[str]],
            threshold: float, filtered: bool = False) -> dict:
    """Classify every current case. Returns lists of names plus `failed` (bool) and `reasons`."""
    report = {"flipped": [], "improved": [], "new": [], "steady": [], "below_threshold": [],
              "expected_fail": [], "expected_fail_now_passing": [], "missing": [], "reasons": []}
    for name in sorted(current):
        cur, base = current[name], baseline.get(name)
        excused = EXPECTED_FAIL in tags.get(name, set()) and not all_passed(base)
        if excused:
            report["expected_fail"].append(name)
            if all_passed(cur):
                report["expected_fail_now_passing"].append(name)
            continue
        if base is None:
            report["new"].append(name)
        elif all_passed(base) and not all_passed(cur):
            report["flipped"].append(name)
        elif cur.get("pass_rate", 0.0) > base.get("pass_rate", 0.0) + 1e-9:
            report["improved"].append(name)
        else:
            report["steady"].append(name)
        if cur.get("score", 0.0) < threshold - 1e-9:
            report["below_threshold"].append(name)
    report["missing"] = sorted(set(baseline) - set(current))
    if report["missing"] and not filtered:
        report["reasons"].append("%d baseline case(s) missing from this run" % len(report["missing"]))
    if report["flipped"]:
        report["reasons"].append("%d case(s) flipped from all-pass to a failed run" % len(report["flipped"]))
    if report["below_threshold"]:
        report["reasons"].append("%d case(s) scored below the %.2f threshold" % (len(report["below_threshold"]), threshold))
    report["failed"] = bool(report["reasons"])
    return report


def baseline_doc(current: dict[str, dict]) -> dict:
    return {"schema": 1, "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cases": {k: current[k] for k in sorted(current)}}


def read_baseline(path: Path) -> dict[str, dict]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    cases = doc.get("cases") if isinstance(doc, dict) else None
    return cases if isinstance(cases, dict) else {}


def _fmt(summary: dict) -> str:
    if summary.get("runs"):
        return "%d/%d runs, score %.2f" % (summary["passed"], summary["runs"], summary.get("score", 0.0))
    return "score %.2f" % summary.get("score", 0.0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="flip.py")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("compare")
    c.add_argument("--results", required=True)
    c.add_argument("--baseline", required=True)
    c.add_argument("--evals-dir", required=True)
    c.add_argument("--threshold", type=float, default=0.8)
    c.add_argument("--exit-code", type=int, default=0, help="exit status of claude plugin eval")
    c.add_argument("--update-baseline", action="store_true",
                   default=os.environ.get("MAGICIAN_EVAL_UPDATE_BASELINE") == "1")
    c.add_argument("--force-baseline", action="store_true",
                   help="with --update-baseline: write the baseline even from a failed run")
    c.add_argument("--tag-filtered", action="store_true",
                   default=os.environ.get("MAGICIAN_EVAL_TAG_FILTERED") == "1",
                   help="the run was filtered by tag, so baseline cases left out are not failures")
    args = ap.parse_args(argv)
    if args.cmd != "compare":
        ap.print_usage(sys.stderr)
        return 2

    if args.exit_code not in (0, 1):
        print("eval run did not complete (exit %d: 2 partial or cost ceiling, 130/143 interrupted)" % args.exit_code)
        return 1
    try:
        doc = json.loads(Path(args.results).read_text(encoding="utf-8"))
        current = parse_results(doc)
    except (OSError, ValueError) as exc:
        print("cannot read eval results %s: %s" % (args.results, exc))
        return 1
    problems = load_errors(doc)
    baseline = read_baseline(Path(args.baseline))
    tags = case_tags(Path(args.evals_dir))
    report = compare(baseline, current, tags, args.threshold, filtered=args.tag_filtered)

    for name in report["flipped"]:
        print("flipped: %s (baseline %s, now %s)" % (name, _fmt(baseline[name]), _fmt(current[name])))
    for name in report["improved"]:
        print("improved: %s (baseline %s, now %s)" % (name, _fmt(baseline[name]), _fmt(current[name])))
    for name in report["new"]:
        print("new: %s (%s)" % (name, _fmt(current[name])))
    for name in report["expected_fail"]:
        note = " - now passes every run: remove the expected-fail tag" if name in report["expected_fail_now_passing"] else ""
        print("expected-fail: %s (%s)%s" % (name, _fmt(current[name]), note))
    for name in report["below_threshold"]:
        print("below threshold: %s (%s)" % (name, _fmt(current[name])))
    for name in report["missing"]:
        if args.tag_filtered:
            print("not run this time (tag-filtered run): %s" % name)
        else:
            print("missing: %s (in the baseline, not in this run)" % name)
    for p in problems:
        print(p)
    print("cases: %d (%d steady, %d improved, %d new, %d flipped, %d expected-fail)" % (
        len(current), len(report["steady"]), len(report["improved"]), len(report["new"]),
        len(report["flipped"]), len(report["expected_fail"])))

    failed = report["failed"] or bool(problems)
    if args.exit_code == 1 and not failed:
        # The CLI fails a run when any case is under the threshold. Accept that only when every such
        # case is an excused expected-fail case.
        excused_low = [n for n in report["expected_fail"] if current[n].get("score", 0.0) < args.threshold - 1e-9]
        if not excused_low:
            print("claude plugin eval exited 1 and no case explains it (load failure or harness error?)")
            failed = True
    if args.update_baseline and failed and not args.force_baseline:
        print("baseline NOT updated: this run failed the tier; fix it, or pass --force-baseline to record it anyway")
    elif args.update_baseline:
        cases = {**baseline, **current} if args.tag_filtered else current
        Path(args.baseline).write_text(json.dumps(baseline_doc(cases), indent=2) + "\n", encoding="utf-8")
        print("baseline updated: %s%s" % (args.baseline, " (forced from a failed run)" if failed else ""))
    elif not baseline:
        print("no baseline yet: run with --update-baseline (or MAGICIAN_EVAL_UPDATE_BASELINE=1) to record one")
    for reason in report["reasons"]:
        print("FAIL: " + reason)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
