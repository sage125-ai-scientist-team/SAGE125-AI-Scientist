import type { FrontendState } from "@streamlit/component-v2-lib";

export type StatsStatus = "loading" | "calculated" | "error";
export type CoverageStatus = "calculated" | "unavailable" | "error" | null;

export interface SageLandingData {
  question_count: number | null;
  evidence_count: number | null;
  plan_count: number | null;
  coverage: number | null;
  coverage_status: CoverageStatus;
  stats_status: StatsStatus;
  q028_available: boolean;
}

export interface SageLandingState extends FrontendState {
  enter_workspace: number | null;
  view_q028: number | null;
}

export type CtaEvent = "enter_workspace" | "view_q028";
