# Assembl evaluation run `20261026T153223Z-174891`

> **PIPELINE DEMONSTRATION - NOT RESEARCH EVIDENCE.**
> These numbers come from synthetic scenarios and/or simulated ratings. They show that the
> evaluation pipeline runs; they do not show that any method is better than another.

- WARNING: Dataset contains SYNTHETIC scenarios; results describe the pipeline, not real students.
- WARNING: Ratings are SIMULATED by a rule that overlaps with Assembl's features; metric differences are circular and are NOT evidence for or against any method.
- WARNING: No human suitability judgments: NDCG@5 and Precision@5 against real raters are not measured.

## Dataset

- Scenarios: 30 (provenance: {'synthetic': 30}; judgments: {'simulated': 30})
- Judged scenarios: 30; single-member teams: 12; multi-member teams: 18
- Split (seed 13): 15 development / 15 test scenarios in 6 leakage groups
- Encoder: `sentence-transformers/all-MiniLM-L6-v2`

## Weights

- **M5** (calibrated): sem=0.20, gap=0.50, role=0.10, avail=0.10, work=0.10; dev NDCG@5 = 0.901
- **M5 without sem** (calibrated): gap=0.50, role=0.20, avail=0.30, work=0.00; dev NDCG@5 = 0.897
- **M5 without gap** (calibrated): sem=0.00, role=0.50, avail=0.50, work=0.00; dev NDCG@5 = 0.873
- **M5 without role** (calibrated): sem=0.40, gap=0.40, avail=0.10, work=0.10; dev NDCG@5 = 0.792
- **M5 without avail** (calibrated): sem=0.10, gap=0.60, role=0.20, work=0.10; dev NDCG@5 = 0.886
- **M5 without work** (calibrated): sem=0.00, gap=0.50, role=0.20, avail=0.30; dev NDCG@5 = 0.897

## Planned comparison on test scenarios (Table 2)

| Method | NDCG@5 | Precision@5 | Added skill coverage@5 | Constraint violations (%) | Mandatory violations | n (NDCG) |
|---|---|---|---|---|---|---|
| M1 (Skill overlap) | 0.751 | 0.129 | 0.153 | 48.6% | 0 | 14 |
| M2 (TF-IDF) | 0.744 | 0.129 | 0.132 | 45.7% | 0 | 14 |
| M3 (Semantic only) | 0.818 | 0.143 | 0.130 | 48.6% | 0 | 14 |
| M4 (Semantic + skill gap) | 0.835 | 0.143 | 0.163 | 48.6% | 0 | 14 |
| M5 (Full Assembl) | 0.911 | 0.143 | 0.159 | 40.0% | 0 | 14 |
| M5 (initial weights) (Full Assembl, paper's initial weights) | 0.903 | 0.143 | 0.139 | 34.3% | 0 | 14 |

Median response time per request (warm cache, full Assembl): 9.3 ms

## Ablations (Table 3)

| Method | NDCG@5 | Precision@5 | Added skill coverage@5 | Constraint violations (%) | Mandatory violations | n (NDCG) |
|---|---|---|---|---|---|---|
| M5  | 0.911 | 0.143 | 0.159 | 40.0% | 0 | 14 |
| M5 without sem  | 0.913 | 0.157 | 0.134 | 35.7% | 0 | 14 |
| M5 without gap  | 0.879 | 0.143 | 0.101 | 28.6% | 0 | 14 |
| M5 without role  | 0.849 | 0.143 | 0.160 | 47.1% | 0 | 14 |
| M5 without avail  | 0.889 | 0.129 | 0.141 | 34.3% | 0 | 14 |
| M5 without work  | 0.913 | 0.157 | 0.134 | 35.7% | 0 | 14 |

## Paired comparisons of per-scenario NDCG@5 (Wilcoxon signed-rank)

| Comparison (a vs b) | n | mean diff (b - a) | rank-biserial | p | note |
|---|---|---|---|---|---|
| RQ2: M3 vs M4 | 14 | 0.017 | 0.333 | 0.3652 |  |
| RQ3: M4 vs M5 | 14 | 0.076 | 0.855 | 0.0137 |  |
| M1 vs M5 | 14 | 0.161 | 1.000 | 0.0005 |  |
| M2 vs M5 | 14 | 0.168 | 0.923 | 0.0024 |  |
| M3 vs M5 | 14 | 0.094 | 0.818 | 0.0137 |  |
| M5 vs M5 without sem | 14 | 0.001 | 0.051 | 0.9097 |  |
| M5 vs M5 without gap | 14 | -0.032 | -0.394 | 0.2783 |  |
| M5 vs M5 without role | 14 | -0.062 | -0.822 | 0.0273 | only 9 non-zero pairs; the test has very little power |
| M5 vs M5 without avail | 14 | -0.023 | -0.455 | 0.2324 |  |
| M5 vs M5 without work | 14 | 0.001 | 0.051 | 0.9097 |  |

## Inter-rater reliability

Krippendorff's alpha (ordinal): 0.533 over 720 pairable units.

## Response time

- Warm cache median: 9.3 ms; cold cache median: 348.8 ms
- Includes: eligibility, feature computation, scoring, explanations; warm = cached embeddings, cold = encoding the project and every candidate text. Excludes database retrieval.
- Hardware: AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD / Windows 10 / Python 3.10.11

## Robustness

- Changed membership: team-independent methods unchanged = **True**; mean Kendall tau per method: M1=1.00, M2=1.00, M3=1.00, M4=0.93, M5=0.92
- Already-covered requirements: 15/15 scenarios behaved as specified
- Inconsistent labels: 15/15 rankings identical after alias rewriting; distinct technologies kept separate: True
- Limited availability: 2 test scenarios qualify
- Incomplete profiles (hide 20%): mean change in NDCG@5 - M1=-0.006, M2=+0.005, M3=+0.004, M4=-0.001, M5=-0.004
- Incomplete profiles (hide 40%): mean change in NDCG@5 - M1=-0.143, M2=-0.121, M3=-0.135, M4=-0.124, M5=-0.179
