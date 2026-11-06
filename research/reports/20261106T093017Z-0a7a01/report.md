# Assembl evaluation run `20261106T093017Z-0a7a01`

> **PIPELINE DEMONSTRATION - NOT RESEARCH EVIDENCE.**
> These numbers come from synthetic scenarios and/or simulated ratings. They show that the
> evaluation pipeline runs; they do not show that any method is better than another.

- WARNING: Dataset contains SYNTHETIC scenarios; results describe the pipeline, not real students.
- WARNING: Ratings are SIMULATED by a rule that overlaps with Assembl's features; metric differences are circular and are NOT evidence for or against any method.
- WARNING: No human suitability judgments: NDCG@5 and Precision@5 against real raters are not measured.

## Dataset

- Scenarios: 60 (provenance: {'synthetic': 60}; judgments: {'simulated': 60})
- Judged scenarios: 60; single-member teams: 24; multi-member teams: 36
- Split (seed 13): 30 development / 30 test scenarios in 12 leakage groups
- Encoder: `sentence-transformers/all-MiniLM-L6-v2`

## Weights

- **M5** (calibrated): sem=0.00, gap=0.70, role=0.20, avail=0.10, work=0.00; dev NDCG@5 = 0.923
- **M5 without sem** (calibrated): gap=0.70, role=0.20, avail=0.10, work=0.00; dev NDCG@5 = 0.923
- **M5 without gap** (calibrated): sem=0.00, role=0.50, avail=0.50, work=0.00; dev NDCG@5 = 0.882
- **M5 without role** (calibrated): sem=0.20, gap=0.60, avail=0.20, work=0.00; dev NDCG@5 = 0.843
- **M5 without avail** (calibrated): sem=0.10, gap=0.70, role=0.20, work=0.00; dev NDCG@5 = 0.912
- **M5 without work** (calibrated): sem=0.00, gap=0.70, role=0.20, avail=0.10; dev NDCG@5 = 0.923

## Planned comparison on test scenarios (Table 2)

| Method | NDCG@5 | Precision@5 | Added skill coverage@5 | Constraint violations (%) | Mandatory violations | n (NDCG) |
|---|---|---|---|---|---|---|
| M1 (Skill overlap) | 0.745 | 0.119 | 0.128 | 60.0% | 0 | 27 |
| M2 (TF-IDF) | 0.713 | 0.089 | 0.089 | 51.9% | 0 | 27 |
| M3 (Semantic only) | 0.686 | 0.096 | 0.078 | 50.4% | 0 | 27 |
| M4 (Semantic + skill gap) | 0.779 | 0.111 | 0.134 | 53.3% | 0 | 27 |
| M5 (Full Assembl) | 0.875 | 0.156 | 0.125 | 36.3% | 0 | 27 |
| M5 (initial weights) (Full Assembl, paper's initial weights) | 0.880 | 0.141 | 0.115 | 33.3% | 0 | 27 |

Median response time per request (warm cache, full Assembl): 4.2 ms

## Ablations (Table 3)

| Method | NDCG@5 | Precision@5 | Added skill coverage@5 | Constraint violations (%) | Mandatory violations | n (NDCG) |
|---|---|---|---|---|---|---|
| M5  | 0.875 | 0.156 | 0.125 | 36.3% | 0 | 27 |
| M5 without sem  | 0.875 | 0.156 | 0.125 | 36.3% | 0 | 27 |
| M5 without gap  | 0.868 | 0.156 | 0.090 | 23.0% | 0 | 27 |
| M5 without role  | 0.809 | 0.126 | 0.134 | 51.9% | 0 | 27 |
| M5 without avail  | 0.866 | 0.156 | 0.124 | 37.8% | 0 | 27 |
| M5 without work  | 0.875 | 0.156 | 0.125 | 36.3% | 0 | 27 |

## Paired comparisons of per-scenario NDCG@5 (Wilcoxon signed-rank)

| Comparison (a vs b) | n | mean diff (b - a) | rank-biserial | p | note |
|---|---|---|---|---|---|
| RQ2: M3 vs M4 | 27 | 0.093 | 0.636 | 0.0074 |  |
| RQ3: M4 vs M5 | 27 | 0.096 | 0.893 | 0.0000 |  |
| M1 vs M5 | 27 | 0.130 | 0.913 | 0.0000 |  |
| M2 vs M5 | 27 | 0.162 | 0.953 | 0.0000 |  |
| M3 vs M5 | 27 | 0.189 | 0.993 | 0.0000 |  |
| M5 vs M5 without sem | 27 | 0.000 | - | - | all paired differences are zero; test not applicable |
| M5 vs M5 without gap | 27 | -0.007 | 0.056 | 0.8382 |  |
| M5 vs M5 without role | 27 | -0.065 | -0.697 | 0.0038 |  |
| M5 vs M5 without avail | 27 | -0.009 | -0.394 | 0.2783 |  |
| M5 vs M5 without work | 27 | 0.000 | - | - | all paired differences are zero; test not applicable |

## Inter-rater reliability

Krippendorff's alpha (ordinal): 0.520 over 1440 pairable units.

## Response time

- Warm cache median: 4.2 ms; cold cache median: 233.7 ms
- Includes: eligibility, feature computation, scoring, explanations; warm = cached embeddings, cold = encoding the project and every candidate text. Excludes database retrieval.
- Hardware: AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD / Windows 10 / Python 3.10.11

## Robustness

- Changed membership: team-independent methods unchanged = **True**; mean Kendall tau per method: M1=1.00, M2=1.00, M3=1.00, M4=0.82, M5=0.82
- Already-covered requirements: 30/30 scenarios behaved as specified
- Inconsistent labels: 30/30 rankings identical after alias rewriting; distinct technologies kept separate: True
- Limited availability: 2 test scenarios qualify
- Incomplete profiles (hide 20%): mean change in NDCG@5 - M1=-0.036, M2=-0.020, M3=+0.008, M4=-0.011, M5=-0.013
- Incomplete profiles (hide 40%): mean change in NDCG@5 - M1=-0.074, M2=-0.044, M3=-0.058, M4=-0.053, M5=-0.069
