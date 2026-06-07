import type { ExecutionResult as ExecResult } from "@/lib/types";

const ACTION_LABELS: Record<string, string> = {
  book_venue: "门票预订",
  reserve_restaurant: "餐厅预约",
  order_food: "点餐/套餐",
  share_message: "分享消息",
};

const STATUS_CLS: Record<string, string> = {
  success: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-700",
  skipped: "bg-gray-100 text-gray-500",
};

interface Props {
  results: ExecResult[];
}

export default function ExecutionResult({ results }: Props) {
  return (
    <div className="space-y-2">
      {results.map((r, i) => (
        <div key={i} className="flex items-start gap-3 rounded-lg border p-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-gray-900">
                {ACTION_LABELS[r.action_type] ?? r.action_type}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_CLS[r.status] ?? "bg-gray-100 text-gray-600"}`}>
                {r.status}
              </span>
            </div>
            {r.booking_id && (
              <p className="text-xs text-gray-500 mt-1">
                预订号：<span className="font-mono text-gray-700">{r.booking_id}</span>
              </p>
            )}
            {r.message && (
              <p className="text-xs text-gray-500 mt-0.5">{r.message}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
