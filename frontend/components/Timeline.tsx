import type { PlanStep } from "@/lib/types";

const STEP_ICONS: Record<string, string> = {
  travel: "🚗",
  activity: "🎯",
  meal: "🍽",
  return: "🏠",
  buffer: "⏸",
};

interface Props {
  steps: PlanStep[];
}

export default function Timeline({ steps }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-xs text-gray-400">
            <th className="text-left pb-2 pr-3 font-medium">类型</th>
            <th className="text-left pb-2 pr-3 font-medium">活动</th>
            <th className="text-left pb-2 pr-3 font-medium whitespace-nowrap">时间段</th>
            <th className="text-left pb-2 font-medium whitespace-nowrap">时长</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {steps.map((step, i) => (
            <tr key={i} className="py-2">
              <td className="py-2 pr-3 text-base">
                {STEP_ICONS[step.step_type] ?? "📌"}
              </td>
              <td className="py-2 pr-3">
                <div className="font-medium text-gray-900">{step.title}</div>
                {step.notes && (
                  <div className="text-xs text-gray-400 mt-0.5">{step.notes}</div>
                )}
              </td>
              <td className="py-2 pr-3 whitespace-nowrap text-gray-600">
                {step.start_time}–{step.end_time}
              </td>
              <td className="py-2 whitespace-nowrap text-gray-500">
                {step.duration_minutes} 分钟
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
