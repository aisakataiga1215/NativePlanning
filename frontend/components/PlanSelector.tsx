import type { ItineraryPlan } from "@/lib/types";
import PlanCard from "./PlanCard";

interface Props {
  plans: ItineraryPlan[];
  selectedId: string;
  onChange: (id: string) => void;
}

export default function PlanSelector({ plans, selectedId, onChange }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-semibold text-gray-500">备选方案</p>
      <div className="flex flex-col gap-2">
        {plans.map((plan) => (
          <button
            key={plan.id}
            onClick={() => onChange(plan.id)}
            className={`text-left rounded-lg border transition-colors ${
              plan.id === selectedId
                ? "border-brand-500 ring-1 ring-brand-500"
                : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <PlanCard plan={plan} compact />
          </button>
        ))}
      </div>
    </div>
  );
}
