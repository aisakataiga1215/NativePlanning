import type {
  GenerateResponse,
  ExecuteResponse,
  ItineraryPlan,
  UserIntent,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path} failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<T>;
}

export function generate(userInput: string): Promise<GenerateResponse> {
  return post<GenerateResponse>("/api/plans/generate", {
    user_input: userInput,
  });
}

export function revise(
  revisionText: string,
  intent: UserIntent,
  currentPlan: ItineraryPlan
): Promise<GenerateResponse> {
  return post<GenerateResponse>("/api/plans/revise", {
    revision_text: revisionText,
    intent,
    current_plan: currentPlan,
  });
}

export function execute(
  plan: ItineraryPlan,
  intent: UserIntent
): Promise<ExecuteResponse> {
  return post<ExecuteResponse>("/api/plans/execute", { plan, intent });
}
