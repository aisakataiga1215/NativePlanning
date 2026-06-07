import type { ItineraryPlan } from "@/lib/types";

interface Props {
  plan: ItineraryPlan;
  compact?: boolean;
}

const SCORE_LABELS = [
  { key: "distance_score", label: "距离" },
  { key: "group_fit_score", label: "适配" },
  { key: "restaurant_score", label: "餐饮" },
  { key: "time_score", label: "时间" },
  { key: "execution_score", label: "可行" },
] as const;

export default function PlanCard({ plan, compact = false }: Props) {
  const pct = Math.round(plan.score * 100);

  return (
    <div className="rounded-lg border bg-white shadow-sm p-4 space-y-3">
      {/* header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-gray-900">{plan.title}</h3>
          <p className="text-sm text-gray-500 mt-0.5">{plan.summary}</p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold text-brand-500">{pct}</div>
          <div className="text-xs text-gray-400">综合评分</div>
        </div>
      </div>

      {/* feasibility */}
      {!plan.feasible && (
        <div className="text-xs bg-red-50 text-red-700 rounded p-2">
          ⚠ 不可行：{plan.infeasible_reasons.join("；")}
        </div>
      )}

      {!compact && (
        <>
          {/* score breakdown */}
          <div className="grid grid-cols-5 gap-1">
            {SCORE_LABELS.map(({ key, label }) => {
              const val = plan.score_breakdown[key];
              const w = Math.round(val * 100);
              return (
                <div key={key} className="flex flex-col items-center gap-1">
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className="bg-brand-500 h-1.5 rounded-full"
                      style={{ width: `${w}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500">{label}</span>
                </div>
              );
            })}
          </div>

          {/* reasons */}
          {plan.reasons.length > 0 && (
            <ul className="text-sm text-gray-700 space-y-1">
              {plan.reasons.map((r, i) => (
                <li key={i} className="flex gap-1.5">
                  <span className="text-brand-500 shrink-0">✓</span>
                  {r}
                </li>
              ))}
            </ul>
          )}

          {/* warnings */}
          {plan.warnings.length > 0 && (
            <ul className="text-xs text-amber-700 bg-amber-50 rounded p-2 space-y-0.5">
              {plan.warnings.map((w, i) => (
                <li key={i}>⚠ {w}</li>
              ))}
            </ul>
          )}

          {/* meta */}
          <div className="flex gap-4 text-xs text-gray-400">
            <span>⏱ {plan.total_duration_minutes} 分钟</span>
            <span>💰 约 ¥{plan.estimated_total_cost}</span>
          </div>
        </>
      )}
    </div>
  );
}
