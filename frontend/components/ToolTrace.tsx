"use client";

import { useState } from "react";
import type { TraceEntry } from "@/lib/types";

const STATUS_ICON: Record<string, string> = {
  success: "✓",
  error: "✗",
  skipped: "–",
};

const STATUS_CLS: Record<string, string> = {
  success: "text-green-600",
  error: "text-red-600",
  skipped: "text-gray-400",
};

interface Props {
  traces: TraceEntry[];
}

export default function ToolTrace({ traces }: Props) {
  const [open, setOpen] = useState<number | null>(null);

  if (traces.length === 0) return null;

  return (
    <div className="space-y-1">
      <p className="text-sm font-semibold text-gray-500">工具调用链</p>
      <div className="rounded-lg border divide-y text-sm">
        {traces.map((t, i) => (
          <div key={i}>
            <button
              onClick={() => setOpen(open === i ? null : i)}
              className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-50 transition-colors"
            >
              <span className={`font-mono text-xs shrink-0 ${STATUS_CLS[t.status] ?? "text-gray-500"}`}>
                {STATUS_ICON[t.status] ?? "?"}
              </span>
              <span className="font-mono text-xs text-gray-700 flex-1">{t.tool_name}</span>
              <span className="text-xs text-gray-400 shrink-0">{t.elapsed_ms} ms</span>
              <span className="text-xs text-gray-300">{open === i ? "▲" : "▼"}</span>
            </button>
            {open === i && (
              <div className="px-3 pb-3 text-xs text-gray-600 space-y-1">
                {t.error && (
                  <div className="text-red-600">错误：{t.error}</div>
                )}
                {t.output != null && (
                  <pre className="bg-gray-50 rounded p-2 text-xs overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(t.output, null, 2)}
                  </pre>
                )}
                {t.inputs != null && (
                  <pre className="bg-gray-50 rounded p-2 text-xs overflow-x-auto whitespace-pre-wrap">
                    入参：{JSON.stringify(t.inputs, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
