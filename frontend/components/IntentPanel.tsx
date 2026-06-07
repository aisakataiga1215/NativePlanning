import type { UserIntent } from "@/lib/types";

const SCENARIO_LABELS: Record<string, string> = {
  family: "亲子家庭",
  couple: "情侣约会",
  friends: "朋友聚会",
  colleagues: "同事聚餐",
  solo: "独自出行",
  unknown: "通用",
};

const MEAL_POLICY_LABELS: Record<string, string> = {
  required: "含餐饮",
  optional: "餐饮可选",
  excluded: "不吃饭",
};

const TIME_PERIOD_LABELS: Record<string, string> = {
  morning: "上午",
  noon: "中午",
  afternoon: "下午",
  evening: "傍晚",
  night: "夜晚",
  soon: "待会",
  unknown: "",
};

interface Props {
  intent: UserIntent;
}

export default function IntentPanel({ intent }: Props) {
  const sourceLabel =
    intent.source === "llm" ? "[LLM]" : "[rule-based]";
  const sourceCls =
    intent.source === "llm"
      ? "bg-green-100 text-green-800"
      : "bg-gray-100 text-gray-600";

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-semibold text-gray-500">意图解析</span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${sourceCls}`}>
          {sourceLabel}
        </span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-brand-100 text-brand-600 font-medium">
          {SCENARIO_LABELS[intent.scenario_type] ?? intent.scenario_type}
        </span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">
          {MEAL_POLICY_LABELS[intent.meal_policy] ?? intent.meal_policy}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <Row label="人数" value={`${intent.group_size} 人`} />
        <Row
          label="时间"
          value={[
            intent.weekday,
            TIME_PERIOD_LABELS[intent.time_period] || intent.time_period,
            intent.time,
          ]
            .filter(Boolean)
            .join(" · ")}
        />
        <Row label="时长" value={`约 ${intent.duration_hours} 小时`} />
        <Row label="最远距离" value={`${intent.max_distance_km} km`} />
        {intent.requested_activities.length > 0 && (
          <Row label="活动需求" value={intent.requested_activities.join("、")} />
        )}
        {intent.requested_meals.length > 0 && (
          <Row label="餐饮需求" value={intent.requested_meals.join("、")} />
        )}
      </div>

      {intent.warnings.length > 0 && (
        <ul className="text-xs text-amber-700 bg-amber-50 rounded p-2 space-y-0.5">
          {intent.warnings.map((w, i) => (
            <li key={i}>⚠ {w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-1">
      <span className="text-gray-400 shrink-0">{label}:</span>
      <span className="text-gray-800 font-medium">{value}</span>
    </div>
  );
}
