import type { OpportunityType } from "../../api/types";

export const OPPORTUNITY_LABELS: Record<OpportunityType, string> = {
  hackathon: "Hackathon",
  academic: "Academic project",
  research: "Research",
  startup: "Startup / innovation",
  competition: "Competition",
  other: "Other",
};

export const IMPORTANCE_LABELS: Record<number, string> = { 1: "Useful", 2: "Important", 3: "Essential" };

export const PROFICIENCY_SHORT: Record<number, string> = {
  1: "1 · learning",
  2: "2 · one project",
  3: "3 · several / lead",
  4: "4 · advanced",
};

export const REASON_LABELS: Record<string, string> = {
  PROFILE_HIDDEN: "Profile hidden",
  ALREADY_MEMBER: "Already on this team",
  COMMITTED_TO_EVENT_TEAM: "On another team for this event",
  YEAR_NOT_ALLOWED: "Year of study not allowed",
  YEAR_UNVERIFIED: "Year of study not stated",
  MANDATORY_SKILL_NOT_MET: "Below a mandatory skill level",
  MANDATORY_SKILL_UNVERIFIED: "Mandatory skill not stated",
  ROLE_NOT_MATCHED: "Prefers no vacant role (mandatory)",
  ROLE_UNVERIFIED: "Roles not stated",
  AVAILABILITY_NOT_MET: "Too few shared slots (mandatory)",
  AVAILABILITY_UNVERIFIED: "Availability not stated",
};

export const OMIT_LABELS: Record<string, string> = {
  all_requirements_covered: "the team already covers every listed requirement",
  no_vacant_roles: "the team lists no vacant roles",
  team_not_synchronous: "the team does not work synchronously",
  team_availability_not_stated: "no current member has stated availability",
  team_states_no_commitment_or_mode: "the team states no weekly hours or working mode",
};
