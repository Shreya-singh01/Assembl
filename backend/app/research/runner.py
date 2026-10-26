"""End-to-end evaluation run: split -> calibrate on dev -> evaluate on test ->
ablations -> robustness -> reliability -> report.

Integrity rules enforced here:
* calibration only ever sees development scenarios;
* label-based metrics are ``None`` ("not measured") when a scenario has no
  judgments - they are never filled with zeros;
* the report states the dataset's provenance, and any run that involves
  synthetic scenarios or simulated ratings is marked as a pipeline
  demonstration whose numbers are not research findings.
"""

from __future__ import annotations

import platform
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from app.domain.engine import rank_candidates
from app.domain.features import team_slots
from app.domain.models import RecommendationRequest, StudentProfile
from app.domain.scoring import FEATURES, INITIAL_WEIGHTS
from app.domain.semantic import profile_text, project_text
from app.domain.skills import SkillRegistry, default_registry
from app.services.embeddings import Encoder, InMemoryEmbeddingCache, semantic_scores

from . import robustness
from .calibration import calibrate
from .methods import METHOD_NAMES, METHODS, FeatureTable, eligible_pool, run_methods
from .metrics import added_coverage_at_k, judged_at_k, ndcg_at_k, precision_at_k, violations_at_k
from .scenario import Scenario
from .splits import split_scenarios
from .stats import krippendorff_alpha_ordinal, paired_wilcoxon

ABLATIONS = {f"M5 without {f}": tuple(x for x in FEATURES if x != f) for f in FEATURES}


@dataclass
class EvalConfig:
    k: int = 5
    seed: int = 13
    dev_fraction: float = 0.5
    grid_step: float = 0.1
    calibrate: bool = True
    run_robustness: bool = True
    timing_repeats: int = 3
    extra: dict[str, Any] = field(default_factory=dict)


def _mean(xs: list[float | None]) -> tuple[float | None, int]:
    vals = [x for x in xs if x is not None]
    return (sum(vals) / len(vals) if vals else None), len(vals)


class Evaluator:
    def __init__(self, encoder: Encoder, registry: SkillRegistry | None = None):
        self.encoder = encoder
        self.cache = InMemoryEmbeddingCache(encoder)
        self.registry = registry or default_registry()

    def semantic(self, scenario: Scenario, pool: list[StudentProfile]) -> dict[str, float]:
        texts = [project_text(scenario.project), *(profile_text(c) for c in pool)]
        vecs = self.cache.embed_many(texts)
        if vecs[0] is None:
            return {c.user_id: 0.0 for c in pool}
        return semantic_scores(vecs[0], {c.user_id: v for c, v in zip(pool, vecs[1:])})

    # ------------------------------------------------------------------
    def _scenario_metrics(self, s: Scenario, ranking: list[str], pool: list[StudentProfile], k: int) -> dict:
        by_id = {c.user_id: c for c in pool}
        labels = s.labels(set(by_id))
        v = violations_at_k(ranking, s.project, s.team, team_slots(s.project, s.team), by_id, s.committed_elsewhere, k)
        return {
            "ndcg@5": ndcg_at_k(ranking, labels, k),
            "precision@5": precision_at_k(ranking, labels, k),
            "judged@5": judged_at_k(ranking, labels, k),
            "added_coverage@5": added_coverage_at_k(ranking, s.project, s.team, by_id, k),
            "constraint_violations@5": v["soft_violation_rate"],
            "violation_kinds": v["soft_violation_kinds"],
            "mandatory_violations": v["mandatory_violations"],
        }

    @staticmethod
    def _aggregate(per_scenario: dict[str, dict[str, dict]], variants: list[str]) -> dict:
        out = {}
        for m in variants:
            rows = [per_scenario[sid][m] for sid in per_scenario if m in per_scenario[sid]]
            agg: dict[str, Any] = {}
            for metric in ("ndcg@5", "precision@5", "added_coverage@5", "constraint_violations@5", "judged@5"):
                value, n = _mean([r[metric] for r in rows])
                agg[metric] = {"value": value, "n": n, "status": "measured" if value is not None else "not measured"}
            agg["mandatory_violations"] = sum(r["mandatory_violations"] for r in rows)
            out[m] = agg
        return out

    # ------------------------------------------------------------------
    def evaluate(self, scenarios: list[Scenario], config: EvalConfig | None = None) -> dict:
        cfg = config or EvalConfig()
        started = time.perf_counter()
        by_id = {s.scenario_id: s for s in scenarios}
        warnings: list[str] = []
        provenance = sorted({s.provenance for s in scenarios})
        jprov = sorted({s.judgment_provenance for s in scenarios})
        is_demo = "synthetic" in provenance or "simulated" in jprov
        if "synthetic" in provenance:
            warnings.append("Dataset contains SYNTHETIC scenarios; results describe the pipeline, not real students.")
        if "simulated" in jprov:
            warnings.append("Ratings are SIMULATED by a rule that overlaps with Assembl's features; "
                            "metric differences are circular and are NOT evidence for or against any method.")
        if "human" not in jprov:
            warnings.append("No human suitability judgments: NDCG@5 and Precision@5 against real raters are not measured.")
        if any(s.labels() and len(s.raters) < 3 for s in scenarios):
            warnings.append("Some judged scenarios have fewer than the planned three raters.")

        split = split_scenarios(scenarios, cfg.dev_fraction, cfg.seed)
        if split["warning"]:
            warnings.append(split["warning"])
        dev = [by_id[i] for i in split["dev"]]
        test = [by_id[i] for i in split["test"]]

        pools: dict[str, list[StudentProfile]] = {}
        sems: dict[str, dict[str, float]] = {}
        tables: dict[str, FeatureTable] = {}
        excluded: dict[str, int] = {}
        for s in scenarios:
            pool, decisions = eligible_pool(s)
            pools[s.scenario_id] = pool
            excluded[s.scenario_id] = sum(1 for d in decisions if not d.eligible)
            sems[s.scenario_id] = self.semantic(s, pool)
            tables[s.scenario_id] = FeatureTable.build(s, pool, sems[s.scenario_id])

        # --- calibration (development scenarios only) --------------------
        dev_tables = {s.scenario_id: tables[s.scenario_id] for s in dev}
        dev_labels = {s.scenario_id: s.labels({c.user_id for c in pools[s.scenario_id]}) for s in dev}
        calib: dict[str, Any] = {}
        variant_weights: dict[str, dict[str, float]] = {}
        for name, feats in {"M5": FEATURES, **ABLATIONS}.items():
            base = {f: INITIAL_WEIGHTS[f] for f in feats}
            initial = {f: w / sum(base.values()) for f, w in base.items()}
            result = calibrate(dev_tables, dev_labels, feats, cfg.grid_step, cfg.k) if cfg.calibrate else \
                {"weights": None, "note": "calibration disabled"}
            calib[name] = {**result, "initial_weights": initial}
            variant_weights[name] = result["weights"] or initial
            calib[name]["used"] = "calibrated" if result["weights"] else "initial (renormalised)"
        if not calib["M5"]["weights"]:
            warnings.append("Weights were not calibrated (no judged development scenarios); initial paper weights used.")

        # --- test evaluation ---------------------------------------------
        main_variants = [*METHODS, "M5 (initial weights)"]
        ablation_variants = ["M5", *ABLATIONS]
        per_scenario: dict[str, dict[str, dict]] = {}
        rankings_out: dict[str, dict[str, list[str]]] = {}
        for s in test:
            sid = s.scenario_id
            ranks = run_methods(s, pools[sid], sems[sid], variant_weights["M5"], tables[sid])
            ranks["M5 (initial weights)"] = tables[sid].rank(INITIAL_WEIGHTS)[0]
            for name in ABLATIONS:
                table = tables[sid]
                if table.ids and any(variant_weights[name].get(f, 0) > 0 for f in table.available):
                    ranks[name] = table.rank(variant_weights[name])[0]
            per_scenario[sid] = {m: self._scenario_metrics(s, r, pools[sid], cfg.k) for m, r in ranks.items()}
            rankings_out[sid] = {m: r[:10] for m, r in ranks.items()}
            pool_ids = {c.user_id for c in pools[sid]}
            assert all(set(r) <= pool_ids for r in ranks.values()), "a method ranked outside the eligible pool"

        def ndcgs(m: str) -> dict[str, float]:
            return {sid: v[m]["ndcg@5"] for sid, v in per_scenario.items() if m in v and v[m]["ndcg@5"] is not None}

        comparisons = {}
        for a, b, label in [("M3", "M4", "RQ2: M3 vs M4"), ("M4", "M5", "RQ3: M4 vs M5"), ("M1", "M5", "M1 vs M5"),
                            ("M2", "M5", "M2 vs M5"), ("M3", "M5", "M3 vs M5"),
                            *[("M5", ab, f"M5 vs {ab}") for ab in ABLATIONS]]:
            na, nb = ndcgs(a), ndcgs(b)
            common = sorted(set(na) & set(nb))
            comparisons[label] = paired_wilcoxon([na[i] for i in common], [nb[i] for i in common]) if common else \
                {"n": 0, "note": "no test scenarios with NDCG@5 for both methods"}

        # --- reliability ---------------------------------------------------
        all_ratings = [(f"{s.scenario_id}:{j.candidate_id}", j.rater_id, j.rating) for s in scenarios for j in s.judgments]
        reliability = {
            "overall": krippendorff_alpha_ordinal(all_ratings),
            "per_scenario": {s.scenario_id: krippendorff_alpha_ordinal(
                [(j.candidate_id, j.rater_id, j.rating) for j in s.judgments])["alpha"] for s in scenarios if s.judgments},
        }

        # --- timing (median per request) ---------------------------------
        timing = self._timing(test or scenarios, variant_weights["M5"], cfg.timing_repeats)

        # --- robustness ----------------------------------------------------
        rob: dict[str, Any] = {}
        if cfg.run_robustness and test:
            w5 = variant_weights["M5"]
            rob["incomplete_profiles"] = robustness.incomplete_profiles(test, self.semantic, w5, seed=cfg.seed, k=cfg.k)
            rob["inconsistent_labels"] = robustness.label_variants(test, self.registry, self.semantic, w5, cfg.seed)
            limited = robustness.limited_availability(test)
            rob["limited_availability"] = {
                "scenarios": limited,
                "metrics": self._aggregate({sid: per_scenario[sid] for sid in limited}, main_variants) if limited else None,
                "note": None if limited else "no test scenario meets the limited-availability criterion",
            }
            rob["already_covered"] = robustness.already_covered(test, self.semantic, w5)
            rob["changed_membership"] = robustness.changed_membership(test, self.semantic, w5)

        return {
            "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pipeline-demonstration" if is_demo else "measured",
            "is_research_evidence": not is_demo,
            "warnings": warnings,
            "config": {
                "k": cfg.k, "seed": cfg.seed, "dev_fraction": cfg.dev_fraction, "grid_step": cfg.grid_step,
                "calibrate": cfg.calibrate, "encoder": self.encoder.model_id, "initial_weights": dict(INITIAL_WEIGHTS),
                "ndcg_gain": "linear (mean rating), log2 discount, condensed list for unjudged candidates",
                "precision_threshold": 2.0, **cfg.extra,
            },
            "dataset": {
                "scenarios": len(scenarios),
                "provenance": {p: sum(1 for s in scenarios if s.provenance == p) for p in provenance},
                "judgment_provenance": {p: sum(1 for s in scenarios if s.judgment_provenance == p) for p in jprov},
                "judged_scenarios": sum(1 for s in scenarios if s.judgments),
                "single_member_teams": sum(1 for s in scenarios if len(s.team) == 1),
                "multi_member_teams": sum(1 for s in scenarios if len(s.team) > 1),
                "excluded_by_eligibility": excluded,
            },
            "split": split,
            "calibration": calib,
            "method_names": {**METHOD_NAMES, "M5 (initial weights)": "Full Assembl, paper's initial weights"},
            "results": self._aggregate(per_scenario, main_variants),
            "ablations": self._aggregate(per_scenario, ablation_variants),
            "comparisons": comparisons,
            "per_scenario": per_scenario,
            "top10_rankings": rankings_out,
            "reliability": reliability,
            "timing": timing,
            "robustness": rob,
            "elapsed_seconds": time.perf_counter() - started,
        }

    def _timing(self, scenarios: list[Scenario], weights: Mapping[str, float], repeats: int) -> dict:
        warm, cold = [], []
        for s in scenarios:
            pool, _ = eligible_pool(s)
            for _ in range(repeats):
                t0 = time.perf_counter()
                sem = self.semantic(s, pool)  # cached embeddings
                rank_candidates(RecommendationRequest(s.project, s.team, tuple(pool), sem, s.committed_elsewhere), weights)
                warm.append((time.perf_counter() - t0) * 1000)
            fresh = Evaluator(self.encoder, self.registry)
            t0 = time.perf_counter()
            sem = fresh.semantic(s, pool)  # encodes project + every profile
            rank_candidates(RecommendationRequest(s.project, s.team, tuple(pool), sem, s.committed_elsewhere), weights)
            cold.append((time.perf_counter() - t0) * 1000)
        return {
            "median_ms_warm_cache": statistics.median(warm) if warm else None,
            "median_ms_cold_cache": statistics.median(cold) if cold else None,
            "includes": "eligibility, feature computation, scoring, explanations; warm = cached embeddings, "
                        "cold = encoding the project and every candidate text. Excludes database retrieval.",
            "hardware": f"{platform.processor() or platform.machine()} / {platform.system()} {platform.release()} / Python {platform.python_version()}",
            "encoder": self.encoder.model_id,
        }
