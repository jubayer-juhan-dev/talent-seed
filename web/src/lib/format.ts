/** Formatting and labels shared across the app (ported from the first viewer). */

export const fmt = (n: number | null | undefined) => (n == null ? "–" : n.toLocaleString("en-US"));

/** First 10 chars of an ISO date/time, or "–". */
export const day = (s: string | null | undefined) => (s ? s.slice(0, 10) : "–");

const LABEL: Record<string, string> = {
  FULL_TIME: "Full-time",
  PART_TIME: "Part-time",
  ONE_TIME: "One-time",
  ESTABLISHED: "Established",
  EMERGING: "Emerging",
  NEWCOMER: "Newcomer",
  EXCLUSIVE: "Exclusive",
  MULTICHAIN: "Multichain",
  UNKNOWN: "Unknown",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
  NONE: "None",
};
export const label = (v: string | null | undefined) => (v ? (LABEL[v] ?? v) : "–");

export const COHORTS = ["P1", "P2", "P3", "HOLD"] as const;
export type Cohort = (typeof COHORTS)[number];

export const COHORT_DESC: Record<Cohort, string> = {
  P1: "Full-time, more than 1 year of tenure",
  P2: "Full-time newcomer or experienced part-timer",
  P3: "Part-time newcomer or one-time",
  HOLD: "Inactive in last 84 days, bot or unknown",
};

export const ATTRIBUTION = "Data from Electric Capital Open Dev Data, licensed CC BY 4.0.";
