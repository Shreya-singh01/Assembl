// Shapes returned by the FastAPI backend (see /api/docs).

export type Role = "student" | "rater" | "admin";
export type WorkMode = "online" | "offline" | "hybrid";
export type OpportunityType = "hackathon" | "academic" | "research" | "startup" | "competition" | "other";

export interface User {
  id: string;
  email: string;
  display_name: string;
  handle: string;
  role: Role;
  created_at: string;
  consent: { terms_accepted_at?: string; research_participation?: boolean };
  profile_complete: boolean;
}

export interface Skill {
  label: string;
  proficiency: number;
  kind: "technical" | "non_technical";
  recognized?: boolean;
}

export interface ProjectSummary {
  title: string;
  summary: string;
  contribution: string;
  link: string | null;
}

export interface Completion {
  percent: number;
  missing: string[];
  ready_for_matching: boolean;
}

export interface Profile {
  user_id: string;
  year: number | null;
  branch: string | null;
  skills: Skill[];
  declared_absent: string[];
  primary_roles: string[];
  secondary_roles: string[];
  interests: string[];
  projects: ProjectSummary[];
  links: string[];
  availability: string[] | null;
  weekly_hours: number | null;
  work_mode: WorkMode | null;
  visible: boolean;
  completion: Completion;
  updated_at: string | null;
  normalization: { original: string; canonical: string; rule: string }[];
}

export interface PublicProfile {
  user_id: string;
  display_name: string;
  handle: string | null;
  year: number | null;
  branch: string | null;
  skills: Skill[];
  primary_roles: string[];
  secondary_roles: string[];
  interests: string[];
  projects: ProjectSummary[];
  links: string[];
  weekly_hours: number | null;
  work_mode: WorkMode | null;
  availability_stated: boolean;
}

export interface Requirement {
  skill: string;
  importance: 1 | 2 | 3;
  desired_proficiency: number;
  mandatory: boolean;
}

export interface Member {
  user_id: string;
  display_name: string;
  handle: string | null;
  role: string | null;
  joined_at: string;
  is_owner: boolean;
}

export interface Project {
  id: string;
  owner_id: string;
  title: string;
  description: string;
  opportunity_type: OpportunityType;
  event_key: string | null;
  requirements: Requirement[];
  target_size: number;
  open_positions: number;
  vacant_roles: string[];
  allowed_years: number[] | null;
  role_mandatory: boolean;
  synchronous: boolean;
  min_shared_slots: number;
  availability_policy: "all" | "majority";
  availability_mandatory: boolean;
  weekly_hours: number | null;
  work_mode: WorkMode | null;
  unverifiable_policy: "exclude" | "include";
  visibility: "public" | "private";
  status: "open" | "closed";
  members: Member[];
  created_at: string;
  updated_at: string;
  version: number;
  viewer: { is_owner?: boolean; is_member?: boolean; pending_invitation?: { id: string; kind: string } | null };
}

export interface ProjectInput {
  title: string;
  description: string;
  opportunity_type: OpportunityType;
  event_key: string | null;
  requirements: Requirement[];
  target_size: number;
  creator_role: string | null;
  vacant_roles: string[];
  allowed_years: number[] | null;
  role_mandatory: boolean;
  synchronous: boolean;
  min_shared_slots: number;
  availability_policy: "all" | "majority";
  availability_mandatory: boolean;
  weekly_hours: number | null;
  work_mode: WorkMode | null;
  unverifiable_policy: "exclude" | "include";
  visibility: "public" | "private";
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface BriefUser {
  id: string | null;
  display_name: string;
  handle: string | null;
}

export interface Invitation {
  id: string;
  project_id: string;
  project_title: string;
  kind: "invite" | "request";
  from_user: BriefUser;
  candidate: BriefUser;
  role: string | null;
  message: string;
  status: "pending" | "accepting" | "accepted" | "declined" | "cancelled" | "expired";
  reason: string | null;
  created_at: string;
  responded_at: string | null;
}

export interface SkillCoverage {
  skill: string;
  importance: number;
  importance_label: string;
  desired_proficiency: number;
  best_proficiency: number;
  coverage: number;
  mandatory: boolean;
}

export interface TeamCoverage {
  overall: number;
  complete: boolean;
  per_skill: SkillCoverage[];
}

export type FeatureKey = "sem" | "gap" | "role" | "avail" | "work";

export interface FeatureValue {
  value: number | null;
  status: "computed" | "neutral_unknown" | "omitted";
}

export interface ExplanationSkill {
  skill: string;
  importance: number;
  importance_label: string;
  desired_proficiency: number;
  candidate_proficiency: number | null;
  candidate_status: "stated" | "absent" | "unknown";
  team_best_before: number;
  coverage_before: number;
  coverage_after: number;
  fully_covers?: boolean;
}

export interface Explanation {
  semantic_relevance: number;
  team_coverage_before: number;
  team_coverage_after: number;
  added_coverage: number;
  adds: ExplanationSkill[];
  duplicates: ExplanationSkill[];
  remaining_gaps: ExplanationSkill[];
  all_requirements_covered_before: boolean;
  required_skills_not_stated: string[];
  role: { value: number | null; status: string; match?: string; role?: string; roles_stated?: boolean } | null;
  availability: { value: number | null; status: string; overlap?: number | null; team_slots?: number; required?: number; stated?: boolean } | null;
  work: {
    value: number | null;
    status: string;
    commitment?: number | null;
    mode?: number | null;
    hours?: { candidate: number; team: number };
    modes?: { candidate: string; team: string };
    unknown?: string[];
  } | null;
  contributions: Partial<Record<FeatureKey, { value: number; weight: number; contribution: number }>>;
  omitted_features: Partial<Record<FeatureKey, string>>;
  weights_renormalized: boolean;
  unknowns: string[];
  unverified_rules: { code: string; message: string }[];
  caveats: string[];
}

export interface RankedCandidate {
  rank: number;
  score: number;
  features: Record<FeatureKey, FeatureValue>;
  added_coverage: number;
  coverage_after: number;
  explanation: Explanation;
  explanation_text: string;
  invitation_status: string | null;
  profile: PublicProfile;
}

export interface Recommendations {
  project_id: string;
  status: "ok" | "team_full" | "no_eligible_candidates" | "closed";
  open_positions: number;
  team_size: number;
  team_coverage: TeamCoverage;
  team_slots: number | null;
  configured_weights: Partial<Record<FeatureKey, number>>;
  active_weights: Partial<Record<FeatureKey, number>>;
  feature_labels: Record<FeatureKey, string>;
  omitted_features: Partial<Record<FeatureKey, string>>;
  weights_renormalized: boolean;
  warnings: string[];
  encoder: string;
  pool: { considered: number; eligible: number; excluded: number; excluded_by_reason: Record<string, number> };
  total: number;
  limit: number;
  offset: number;
  candidates: RankedCandidate[];
  notice: string;
}

export interface Conversation {
  id: string;
  kind: "direct" | "team";
  title: string;
  project_id: string | null;
  participants: BriefUser[];
  last_message_at: string | null;
  last_message_preview: string | null;
  unread: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string | null;
  body: string;
  created_at: string;
  client_id: string;
  pending?: boolean;
  failed?: boolean;
}

export interface Dashboard {
  profile_completion: Completion;
  profile_visible: boolean;
  my_projects: Project[];
  pending_received: Invitation[];
  recent_sent: Invitation[];
  recent_conversations: Conversation[];
  suggested_projects: {
    id: string;
    title: string;
    opportunity_type: OpportunityType;
    open_positions: number;
    vacant_roles: string[];
    semantic_relevance: number;
  }[];
}

export interface Vocabulary {
  skills: string[];
  proficiency: Record<string, string>;
  roles: string[];
}
