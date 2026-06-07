// TypeScript interfaces mirroring Pydantic schemas in src/schemas/

export type StepType = "travel" | "activity" | "meal" | "addon" | "return";
export type ScenarioType =
  | "solo"
  | "couple"
  | "family"
  | "friends"
  | "colleagues"
  | "unknown";
export type MealPolicy = "required" | "optional" | "excluded";
export type PlanMode = "activity_first" | "meal_first" | "meal_only";
export type IntentSource = "llm" | "rule_based" | "unknown";

// ── plan.py ────────────────────────────────────────────────────────────────

export interface PlanStep {
  step_type: StepType;
  title: string;
  location_name: string;
  start_time: string; // HH:MM
  end_time: string;   // HH:MM
  duration_minutes: number;
  distance_from_previous_km: number;
  notes: string;
  related_entity_id: string | null;
  travel_minutes: number;
  area: string;
}

export interface ScoreBreakdown {
  distance_score: number;
  time_score: number;
  group_fit_score: number;
  restaurant_score: number;
  execution_score: number;
}

export interface ItineraryPlan {
  id: string;
  title: string;
  scenario_type: ScenarioType;
  summary: string;
  steps: PlanStep[];
  estimated_total_cost: number;
  total_duration_minutes: number;
  score: number;
  score_breakdown: ScoreBreakdown;
  reasons: string[];
  risks: string[];
  warnings: string[];
  required_actions: string[];
  backup_plan_id: string | null;
  venue_id: string | null;
  restaurant_id: string | null;
  venue_ids: string[];
  stop_count: number;
  feasible: boolean;
  infeasible_reasons: string[];
  opening_fit: number;
}

// ── user_intent.py ─────────────────────────────────────────────────────────

export interface UserIntent {
  scenario_type: ScenarioType;
  group_size: number;
  date: string;
  weekday: string;
  time_period: string;
  time: string; // HH:MM
  duration_hours: number;
  max_distance_km: number;
  activity_preferences: string[];
  meal_preferences: string[];
  requested_activities: string[];
  requested_meals: string[];
  requested_places: string[];
  hard_constraints: string[];
  soft_preferences: string[];
  warnings: string[];
  budget_preference: "low" | "medium" | "high";
  meal_policy: MealPolicy;
  plan_mode: PlanMode;
  source: IntentSource;
  raw_input: string | null;
  avoid_venue_ids: string[];
  avoid_restaurant_ids: string[];
  location_anchor: string;
  revision_scope: string;
}

// ── order.py ───────────────────────────────────────────────────────────────

export type ActionType =
  | "book_venue"
  | "reserve_restaurant"
  | "purchase_coupon"
  | "order_addon";

export interface ExecutionResult {
  action_type: string;
  status: "success" | "failed" | "skipped";
  order_id: string | null;
  booking_id: string | null;
  message: string;
  error_reason: string | null;
}

export interface ShareMessage {
  receiver_type: string;
  included_plan_id: string;
  message: string;
}

// ── api/app.py trace shape ─────────────────────────────────────────────────

export interface TraceEntry {
  tool_name: string;
  inputs: unknown;
  output: unknown;
  status: string;
  elapsed_ms: number;
  error: string | null;
}

// ── api/schemas.py ─────────────────────────────────────────────────────────

export interface GenerateResponse {
  plan: ItineraryPlan;
  alternatives: ItineraryPlan[];
  intent: UserIntent;
  traces: TraceEntry[];
  warnings: string[];
}

export interface ExecuteResponse {
  results: ExecutionResult[];
  share_message: ShareMessage;
  traces: TraceEntry[];
}
