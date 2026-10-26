import type { RankedCandidate, Recommendations } from "../api/types";

export function candidate(overrides: Partial<RankedCandidate> & { id: string; name: string; score: number; contributions: Record<string, number> }): RankedCandidate {
  const { id, name, score, contributions, ...rest } = overrides;
  return {
    rank: 1,
    score,
    features: {
      sem: { value: 0.5, status: "computed" },
      gap: { value: 1, status: "computed" },
      role: { value: 1, status: "computed" },
      avail: { value: null, status: "omitted" },
      work: { value: null, status: "omitted" },
    },
    added_coverage: 0.6,
    coverage_after: 1,
    explanation_text: `Adds Node.js (essential; stated proficiency 3 of 4). Proficiency is self-reported.`,
    invitation_status: null,
    explanation: {
      semantic_relevance: 0.5,
      team_coverage_before: 0.4,
      team_coverage_after: 1,
      added_coverage: 0.6,
      adds: [
        {
          skill: "Node.js",
          importance: 3,
          importance_label: "essential",
          desired_proficiency: 3,
          candidate_proficiency: 3,
          candidate_status: "stated",
          team_best_before: 0,
          coverage_before: 0,
          coverage_after: 1,
          fully_covers: true,
        },
      ],
      duplicates: [],
      remaining_gaps: [],
      all_requirements_covered_before: false,
      required_skills_not_stated: [],
      role: { value: 1, status: "computed", match: "primary", role: "Backend" },
      availability: null,
      work: null,
      contributions: Object.fromEntries(
        Object.entries(contributions).map(([k, c]) => [k, { value: c * 2, weight: 0.5, contribution: c }]),
      ),
      omitted_features: { avail: "team_not_synchronous" },
      weights_renormalized: true,
      unknowns: [],
      unverified_rules: [],
      caveats: ["Proficiency is self-reported."],
    },
    profile: {
      user_id: id,
      display_name: name,
      handle: name.toLowerCase(),
      year: 2,
      branch: "CSE",
      skills: [{ label: "Node.js", proficiency: 3, kind: "technical" }],
      primary_roles: ["Backend"],
      secondary_roles: [],
      interests: [],
      projects: [],
      links: [],
      weekly_hours: null,
      work_mode: null,
      availability_stated: false,
    },
    ...rest,
  };
}

export const LABELS = {
  sem: "Semantic relevance",
  gap: "Skill-gap contribution",
  role: "Vacant-role fit",
  avail: "Shared availability",
  work: "Commitment & working mode",
} as const;

export function recommendations(cands: RankedCandidate[]): Recommendations {
  return {
    project_id: "p1",
    status: "ok",
    open_positions: 2,
    team_size: 2,
    team_coverage: {
      overall: 0.4,
      complete: false,
      per_skill: [
        { skill: "React", importance: 2, importance_label: "important", desired_proficiency: 3, best_proficiency: 3, coverage: 1, mandatory: false },
        { skill: "Node.js", importance: 3, importance_label: "essential", desired_proficiency: 3, best_proficiency: 0, coverage: 0, mandatory: false },
      ],
    },
    team_slots: null,
    configured_weights: { sem: 0.3, gap: 0.35, role: 0.15, avail: 0.1, work: 0.1 },
    active_weights: { sem: 0.375, gap: 0.4375, role: 0.1875 },
    feature_labels: { ...LABELS },
    omitted_features: { avail: "team_not_synchronous", work: "team_states_no_commitment_or_mode" },
    weights_renormalized: true,
    warnings: [],
    encoder: "sentence-transformers/all-MiniLM-L6-v2",
    pool: { considered: 3, eligible: 2, excluded: 1, excluded_by_reason: { YEAR_NOT_ALLOWED: 1 } },
    total: cands.length,
    limit: 20,
    offset: 0,
    candidates: cands,
    notice: "Scores rank candidates for this request only. They are not probabilities of team success; proficiency is self-reported.",
  };
}
