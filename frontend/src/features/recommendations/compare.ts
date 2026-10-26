import type { FeatureKey, RankedCandidate } from "../../api/types";

export const FEATURE_ORDER: FeatureKey[] = ["sem", "gap", "role", "avail", "work"];

export const FEATURE_COLORS: Record<FeatureKey, string> = {
  sem: "#5b7f95",
  gap: "#1f6f5c",
  role: "#b4541a",
  avail: "#8a6bb0",
  work: "#a08a3c",
};

export interface FeatureDiff {
  feature: FeatureKey;
  a: number;
  b: number;
  diff: number; // contribution(a) - contribution(b)
}

/** Explain why candidate `a` scores differently from `b`: per-feature
 *  contribution differences (weight x value), largest first. Both candidates
 *  come from the same request, so their active weights are identical. */
export function compareCandidates(a: RankedCandidate, b: RankedCandidate): { total: number; diffs: FeatureDiff[] } {
  const diffs = FEATURE_ORDER.filter((f) => a.explanation.contributions[f] !== undefined).map((f) => {
    const ca = a.explanation.contributions[f]!.contribution;
    const cb = b.explanation.contributions[f]?.contribution ?? 0;
    return { feature: f, a: ca, b: cb, diff: ca - cb };
  });
  diffs.sort((x, y) => Math.abs(y.diff) - Math.abs(x.diff));
  return { total: a.score - b.score, diffs };
}

/** Coverage per skill after adding the candidate, for the coverage chart overlay. */
export function coverageAfter(c: RankedCandidate): Record<string, number> {
  const out: Record<string, number> = {};
  for (const s of c.explanation.adds) out[s.skill] = s.coverage_after;
  return out;
}
