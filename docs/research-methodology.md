# Research methodology: implementation notes

How Assembl's code implements the paper *"Assembl: Team-Aware Candidate Recommendation Using Semantic Skill Matching and Complementarity"*. Equation numbers refer to the paper.

The scoring engine is pure Python in `backend/app/domain/` and has no FastAPI or MongoDB imports. The evaluation pipeline is in `backend/app/research/`.

## Where each part of the paper lives

| Paper | Code |
|---|---|
| §4.1 profile and requirement representation | `domain/models.py` (`StudentProfile`, `Requirement`, `ProjectSpec`) |
| §4.2 alias table | `domain/skills.py`, `domain/skill_aliases.json` |
| Eq. 1, `f_sem` | `domain/semantic.py` (`cosine_clipped`, text templates); encoders in `services/embeddings.py` |
| Eqs. 2–5, coverage, `G(c,T)`, `f_gap` | `domain/coverage.py` |
| §4.4 `f_role`, `f_avail`, `f_work` | `domain/features.py` |
| §4.4 eligibility filter `E(c,P,T)` | `domain/eligibility.py` |
| Eq. 6 score, renormalisation, tie-breaking | `domain/scoring.py` |
| §4.5 explanations | `domain/explanations.py` |
| Fig. 1 pipeline | `domain/engine.py` (`rank_candidates`) |
| §4.5 calibration | `research/calibration.py` |
| §4.6 protocol, §5 methods M1–M5, ablations, robustness | `research/{methods,metrics,stats,splits,pooling,robustness,runner}.py` |

## Ambiguities in the paper and the decisions taken

1. **"Essential" means two different things.** It is importance level 3 (`a_s ∈ {useful, important, essential}`), and separately a requirement "marked as essential (enforced as a rule)". Scenario A has importance-3 skills that do *not* filter candidates out, so the two are kept apart. Importance is `importance`, and the rule is a separate `mandatory` flag. The UI calls the rule "Mandatory" to avoid confusing the two.
2. **What satisfying a mandatory skill means.** The candidate must state a proficiency of at least the desired level `r_s`.
3. **Unknown versus absent information.** Storage keeps them apart: an unlisted skill is *not stated*, and `declared_absent` holds an explicit "none". Availability uses `null` for not stated and `[]` for stated-none. As in Eq. 2, both an unstated and an absent skill contribute 0 to coverage. Explanations still list unstated required skills as "not stated ≠ does not have". `team_coverage(..., unknown_value=x)` exists **only** as a clearly labelled experimental variant.
4. **Mandatory rules that cannot be checked** (the field is blank) produce `*_UNVERIFIED` reason codes, never `*_NOT_MET`. Each project sets an `unverifiable_policy`:
   - `exclude` (the default) does not rank them, because the creator asked for the rule to be satisfied.
   - `include` ranks them with a flag.
5. **`f_role` with several vacant roles** takes the best match (1 if any vacant role is primary, otherwise 0.5 if any is secondary, otherwise 0). It is **omitted** for the request when the team lists no vacant roles. A candidate who stated no roles gets 0, as the paper specifies, and is flagged.
6. **`f_avail`.**
   - `A_T` is the intersection of members' stated slots, or majority-shared slots under the `majority` policy.
   - Members who stated no availability are left out of `A_T`.
   - If no member stated any, the feature is omitted and a warning is shown.
   - A candidate with unstated availability gets 0.5 and is flagged.
   - The feature is omitted for asynchronous teams.
   - `h ≥ 1` is required when the team is synchronous.
7. **`f_work`.**
   - `H_max = 40 − 1 = 39`, the largest difference possible on the 1–40 h form.
   - A component the *team* does not state is left out of the mean.
   - A component the *candidate* does not state gets a flagged 0.5, the same idea as the paper's availability rule.
   - The feature is omitted when the team states neither hours nor mode.
8. **Request-level omission.** A feature is either defined for every candidate in a request or omitted for all of them, so scores stay comparable. Omitted features are dropped and the remaining weights renormalised (`w'_k = w_k / Σ_active w_j`).
9. **Empty profile text.** If a candidate's profile text is empty, `f_sem = 0` and the candidate is flagged.
10. **Tie-breaking.** Score, then `f_gap`, then `f_sem` (all descending), then candidate id. M1–M3 break ties by score, then id only. Using `f_gap` there would make "team-independent" baselines depend on the team.
11. **Vacant roles are a set.** When someone joins with a role, that role is removed. Two vacancies for the same role can't be represented. This matches the paper's limitation that the coverage model ignores workload.

## Evaluation pipeline decisions

- **M1:** `Σ_{s∈S, c states s} a_s / Σ a_s`, ignoring the team.
- **M2:** TF-IDF fitted per scenario on the project text plus the pool's profile texts, then cosine similarity.
- **M4:** the paper's `sem` and `gap` weights (0.30 / 0.35), renormalised to 0.4615 / 0.5385.
- **Same pool for every method.** Mandatory rules are applied once and all methods rank that pool. Mandatory violations in a method's top 5 are counted separately and are always 0.
- **Labels and NDCG.**
  - The label is the mean rating, restricted to *eligible* candidates (only those can be ranked).
  - NDCG uses **linear gain** with a `log2(rank+1)` discount and an ideal ordering over all judged eligible candidates.
  - If the ideal DCG is 0, NDCG is undefined and the scenario is left out of the macro-average. The count `n` is reported.
- **Unjudged candidates** are never scored 0. They are removed from the ranking before the cutoff (the "condensed list"), and `judged@5` is reported.
- **Precision@5:** a candidate is relevant if the mean rating is at least 2. The denominator is `min(5, judged candidates ranked)`.
- **Constraint violations@5:** the share of the top 5 with any *soft* conflict: zero shared availability (when it isn't mandatory), online versus offline, or a stated role preference that matches no vacant role.
- **Splits.** Scenarios that share a base project or any team member are joined by union-find, and whole groups go to a split. The seed and manifest are stored with each run.
- **Calibration.** Grid search over the simplex (step 0.1 by default) using **development scenarios only**. Ties go to the first vector in lexicographic order. A vector that cannot rank some development scenario is skipped. Each ablation is recalibrated. The paper's initial weights are kept as the separate baseline "M5 (initial weights)".
- **Statistics.**
  - Wilcoxon signed-rank test on per-scenario NDCG@5, with the matched-pairs rank-biserial effect size.
  - A warning when fewer than 10 pairs differ.
  - Krippendorff's α (ordinal), with the number of pairable units.
- **Robustness checks.**
  - Hiding 20% and 40% of skills or availability.
  - Rewriting skills with aliases (rankings must stay identical).
  - Scenarios with limited availability.
  - Teams whose coverage is already complete.
  - **Changed membership:** M1–M3 must give τ = 1 over candidates eligible under both teams. The run records whether this holds.

## Research integrity

- Each scenario has a `provenance` (`synthetic`/`real`) and a `judgment_provenance` (`none`/`simulated`/`human`). Any run involving synthetic scenarios or simulated ratings is marked `pipeline-demonstration` with `is_research_evidence: false`. The report then opens with "PIPELINE DEMONSTRATION – NOT RESEARCH EVIDENCE".
- Simulated ratings come from a rule that overlaps with Assembl's own features. Results on them are **circular** and are not evidence.
- Unmeasured metrics print as "not measured", never as a number.
- Human ratings collected in the app are used only offline. They never change live recommendations.
- The weights are the paper's initial design choices. No calibrated-on-real-data weights exist yet.

## Known limitations (inherited from the paper)

- Self-reported proficiency.
- Max-based coverage: no workload modelling and no need for several specialists in one skill.
- One-sided ranking: whether the candidate is interested is not modelled.
- Sequential, not joint, selection.
- Single-institution evaluation, still pending.
