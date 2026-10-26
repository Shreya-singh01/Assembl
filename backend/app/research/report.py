"""Render an evaluation run as Markdown (mirrors the paper's Tables 2 and 3).

Unmeasured cells print "not measured", never a number.
"""

from __future__ import annotations

from typing import Any


def _num(x: float | None, digits: int = 3, signed: bool = False) -> str:
    if x is None:
        return "undefined"
    return f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"


def _cell(m: dict[str, Any], digits: int = 3, pct: bool = False) -> str:
    if m["value"] is None:
        return "not measured"
    v = m["value"] * 100 if pct else m["value"]
    return f"{v:.1f}%" if pct else f"{v:.{digits}f}"


def _table(rows: dict[str, dict], names: dict[str, str], timing_ms: float | None) -> list[str]:
    out = ["| Method | NDCG@5 | Precision@5 | Added skill coverage@5 | Constraint violations (%) | Mandatory violations | n (NDCG) |",
           "|---|---|---|---|---|---|---|"]
    for key, agg in rows.items():
        out.append(
            f"| {key} {names.get(key, '')} | {_cell(agg['ndcg@5'])} | {_cell(agg['precision@5'])} | "
            f"{_cell(agg['added_coverage@5'])} | {_cell(agg['constraint_violations@5'], pct=True)} | "
            f"{agg['mandatory_violations']} | {agg['ndcg@5']['n']} |"
        )
    if timing_ms is not None:
        out.append("")
        out.append(f"Median response time per request (warm cache, full Assembl): {timing_ms:.1f} ms")
    return out


def render_markdown(run: dict[str, Any]) -> str:
    lines = [f"# Assembl evaluation run `{run['run_id']}`", ""]
    if not run["is_research_evidence"]:
        lines += ["> **PIPELINE DEMONSTRATION - NOT RESEARCH EVIDENCE.**",
                  "> These numbers come from synthetic scenarios and/or simulated ratings. They show that the",
                  "> evaluation pipeline runs; they do not show that any method is better than another.", ""]
    for w in run["warnings"]:
        lines.append(f"- WARNING: {w}")
    ds = run["dataset"]
    lines += ["", "## Dataset", "",
              f"- Scenarios: {ds['scenarios']} (provenance: {ds['provenance']}; judgments: {ds['judgment_provenance']})",
              f"- Judged scenarios: {ds['judged_scenarios']}; single-member teams: {ds['single_member_teams']}; "
              f"multi-member teams: {ds['multi_member_teams']}",
              f"- Split (seed {run['split']['seed']}): {len(run['split']['dev'])} development / {len(run['split']['test'])} test "
              f"scenarios in {len(run['split']['groups'])} leakage groups",
              f"- Encoder: `{run['config']['encoder']}`", ""]

    lines += ["## Weights", ""]
    for name, c in run["calibration"].items():
        w = c["weights"] or c["initial_weights"]
        ws = ", ".join(f"{k}={v:.2f}" for k, v in w.items())
        lines.append(f"- **{name}** ({c['used']}): {ws}" + (f"; dev NDCG@5 = {c['dev_ndcg']:.3f}" if c.get("dev_ndcg") else ""))
    lines += ["", "## Planned comparison on test scenarios (Table 2)", ""]
    lines += _table(run["results"], {k: f"({v})" for k, v in run["method_names"].items()},
                    run["timing"]["median_ms_warm_cache"])
    lines += ["", "## Ablations (Table 3)", ""]
    lines += _table(run["ablations"], {}, None)
    lines += ["", "## Paired comparisons of per-scenario NDCG@5 (Wilcoxon signed-rank)", "",
              "| Comparison (a vs b) | n | mean diff (b - a) | rank-biserial | p | note |", "|---|---|---|---|---|---|"]
    for label, c in run["comparisons"].items():
        f = lambda x, d=3: "-" if x is None else f"{x:.{d}f}"  # noqa: E731
        lines.append(f"| {label} | {c.get('n', 0)} | {f(c.get('mean_difference'))} | {f(c.get('rank_biserial'))} | "
                     f"{f(c.get('p_value'), 4)} | {c.get('note') or ''} |")
    rel = run["reliability"]["overall"]
    lines += ["", "## Inter-rater reliability", "",
              f"Krippendorff's alpha (ordinal): {_num(rel['alpha'])} "
              f"over {rel['pairable_units']} pairable units."]
    t = run["timing"]
    lines += ["", "## Response time", "",
              f"- Warm cache median: {_num(t['median_ms_warm_cache'], 1)} ms; cold cache median: {_num(t['median_ms_cold_cache'], 1)} ms",
              f"- Includes: {t['includes']}", f"- Hardware: {t['hardware']}"]
    rob = run.get("robustness") or {}
    if rob:
        lines += ["", "## Robustness", ""]
        cm = rob["changed_membership"]
        lines.append(f"- Changed membership: team-independent methods unchanged = **{cm['team_independent_methods_unchanged']}**; "
                     f"mean Kendall tau per method: " + ", ".join(
                         f"{m}={_num(v, 2)}" for m, v in cm["per_method_mean_kendall_tau"].items()))
        ac = rob["already_covered"]
        lines.append(f"- Already-covered requirements: {ac['passed']}/{ac['scenarios']} scenarios behaved as specified")
        il = rob["inconsistent_labels"]
        lines.append(f"- Inconsistent labels: {il['rankings_identical']}/{il['scenarios_checked']} rankings identical after alias rewriting; "
                     f"distinct technologies kept separate: {all(il['distinct_technologies_kept_separate'].values())}")
        la = rob["limited_availability"]
        lines.append(f"- Limited availability: {len(la['scenarios'])} test scenarios qualify" + (f" ({la['note']})" if la["note"] else ""))
        for share, per in rob["incomplete_profiles"].items():
            lines.append(f"- Incomplete profiles (hide {float(share):.0%}): mean change in NDCG@5 - " + ", ".join(
                f"{m}={_num(v['mean_delta_ndcg@5'], 3, signed=True)}" for m, v in per.items()))
    return "\n".join(lines) + "\n"
