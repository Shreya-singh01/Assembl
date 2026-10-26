"""Research command line.

    python -m app.research.cli generate --out ../research/scenarios/synthetic
    python -m app.research.cli evaluate --scenarios ../research/scenarios/synthetic --out ../research/reports
    python -m app.research.cli pool --scenarios <dir> --out ../research/judging

``--encoder hashing`` swaps in the non-semantic test encoder (fast, offline);
reports record which encoder produced them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.services.embeddings import build_encoder

from .methods import eligible_pool, run_methods
from .pooling import build_pool, judging_packet
from .report import render_markdown
from .runner import EvalConfig, Evaluator
from .scenario import load_scenarios
from .synthetic import generate


def _encoder(name: str | None):
    s = get_settings()
    return build_encoder(name or s.embedding_backend, s.embedding_model)


def cmd_generate(a) -> None:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    scenarios = generate(seed=a.seed, simulate_judgments=not a.no_judgments)
    path = out / "synthetic_scenarios.json"
    path.write_text(json.dumps({"_notice": "SYNTHETIC DATA - not real students; simulated ratings are not human judgments.",
                                "scenarios": scenarios}, indent=1), encoding="utf-8")
    print(f"wrote {len(scenarios)} synthetic scenarios to {path}")


def cmd_evaluate(a) -> None:
    scenarios = load_scenarios([Path(p) for p in a.scenarios])
    ev = Evaluator(_encoder(a.encoder))
    run = ev.evaluate(scenarios, EvalConfig(seed=a.seed, grid_step=a.step, calibrate=not a.no_calibrate,
                                            run_robustness=not a.no_robustness))
    out = Path(a.out) / run["run_id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.json").write_text(json.dumps(run, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(render_markdown(run), encoding="utf-8")
    (out / "split_manifest.json").write_text(json.dumps(run["split"], indent=1), encoding="utf-8")
    print(f"status: {run['status']}")
    for w in run["warnings"]:
        print("WARNING:", w)
    print(f"report: {out / 'report.md'}")


def cmd_pool(a) -> None:
    scenarios = load_scenarios([Path(p) for p in a.scenarios])
    ev = Evaluator(_encoder(a.encoder))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for s in scenarios:
        pool, _ = eligible_pool(s)
        ranks = run_methods(s, pool, ev.semantic(s, pool))
        ids = build_pool(ranks, [c.user_id for c in pool], top_n=10, extra=a.extra, seed=a.seed)
        packet = judging_packet(s, ids)
        key = packet.pop("_label_to_candidate")
        (out / f"{s.scenario_id}.packet.json").write_text(json.dumps(packet, indent=1), encoding="utf-8")
        (out / f"{s.scenario_id}.key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print(f"wrote judging packets (rater view) and keys (coordinator only) for {len(scenarios)} scenarios to {out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="assembl-research")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write synthetic scenarios (clearly labelled)")
    g.add_argument("--out", required=True)
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--no-judgments", action="store_true", help="omit simulated ratings")
    g.set_defaults(fn=cmd_generate)
    e = sub.add_parser("evaluate", help="run the full evaluation protocol")
    e.add_argument("--scenarios", nargs="+", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--seed", type=int, default=13)
    e.add_argument("--step", type=float, default=0.1)
    e.add_argument("--encoder", choices=["sbert", "hashing"])
    e.add_argument("--no-calibrate", action="store_true")
    e.add_argument("--no-robustness", action="store_true")
    e.set_defaults(fn=cmd_evaluate)
    po = sub.add_parser("pool", help="build anonymised judging packets")
    po.add_argument("--scenarios", nargs="+", required=True)
    po.add_argument("--out", required=True)
    po.add_argument("--seed", type=int, default=0)
    po.add_argument("--extra", type=int, default=3)
    po.add_argument("--encoder", choices=["sbert", "hashing"])
    po.set_defaults(fn=cmd_pool)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
