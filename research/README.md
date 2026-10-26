# Research workspace

| Path | Contents |
|---|---|
| `scenarios/synthetic/` | 30 **synthetic** scenarios with **simulated** ratings (6 base projects × 5 team variants; single- and multi-member teams). For exercising the pipeline only. |
| `scenarios/real/` | Put consent-based real scenarios here (JSON, `provenance: "real"`). None exist yet. |
| `reports/<run_id>/` | `report.md`, `run.json` and `split_manifest.json` for each evaluation run. |

## Commands (run from `backend/`)

```bash
# regenerate the synthetic set
.venv/Scripts/python -m app.research.cli generate --out ../research/scenarios/synthetic
# full protocol: split → dev-only calibration → test metrics → ablations → robustness → reliability
.venv/Scripts/python -m app.research.cli evaluate --scenarios ../research/scenarios/real --out ../research/reports
# anonymised rating packets (rater view) and keys (coordinator only)
.venv/Scripts/python -m app.research.cli pool --scenarios ../research/scenarios/real --out ../research/judging
```

`--encoder hashing` swaps in a fast, **non-semantic** test encoder. The report records which encoder produced it.

## Scenario format

```json
{
  "scenario_id": "R01", "base_project_id": "P1",
  "provenance": "real", "judgment_provenance": "human",
  "project": {"project_id": "P1", "title": "...", "description": "...",
              "requirements": [{"skill": "Node.js", "importance": 3, "desired_proficiency": 3, "mandatory": false}],
              "target_size": 4, "vacant_roles": ["Backend"], "synchronous": true, "min_shared_slots": 2,
              "weekly_hours": 10, "work_mode": "hybrid"},
  "team": [{"user_id": "t1", "skills": {"React": 3}, "availability": ["mon-eve"], "primary_roles": ["Frontend"]}],
  "candidates": [{"user_id": "c1", "skills": {"nodejs": 3}, "availability": null}],
  "judgments": [{"rater_id": "r1", "candidate_id": "c1", "rating": 2}]
}
```

- `availability: null` means not stated, and `[]` means stated: none.
- Unlisted skills count as not stated. Use `declared_absent` for an explicit "none".
- Ratings use the 0–3 scale: not / marginally / suitable / strongly suitable. Plan for at least 3 raters per scenario.

## Current status

**Evaluation pending.** No real scenarios or human judgments exist yet.

The run in `reports/` was produced with the real Sentence-BERT encoder on the synthetic set. Its header marks it **PIPELINE DEMONSTRATION – NOT RESEARCH EVIDENCE**. Its simulated ratings come from a rule that overlaps with Assembl's features, so its numbers say nothing about whether Assembl beats any baseline.
