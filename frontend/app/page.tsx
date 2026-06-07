"use client";

import { useState } from "react";
import type {
  ItineraryPlan,
  UserIntent,
  TraceEntry,
  ExecuteResponse,
} from "@/lib/types";
import * as api from "@/lib/api";
import IntentPanel from "@/components/IntentPanel";
import PlanCard from "@/components/PlanCard";
import PlanSelector from "@/components/PlanSelector";
import Timeline from "@/components/Timeline";
import ToolTrace from "@/components/ToolTrace";
import ExecutionResult from "@/components/ExecutionResult";
import ShareMessage from "@/components/ShareMessage";
import RevisionInput from "@/components/RevisionInput";

type Stage =
  | "idle"
  | "generating"
  | "plan_ready"
  | "revising"
  | "executing"
  | "done";

const SAMPLE_INPUTS = [
  "今天下午带孩子去亲子乐园玩，顺便吃个饭",
  "周末和老婆去西湖边逛逛，要有浪漫氛围",
  "今晚和朋友一起吃火锅，5个人",
  "明天下午带家人看个展览，不要太远",
];

export default function Page() {
  const [stage, setStage] = useState<Stage>("idle");
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [intent, setIntent] = useState<UserIntent | null>(null);
  const [plan, setPlan] = useState<ItineraryPlan | null>(null);
  const [alternatives, setAlternatives] = useState<ItineraryPlan[]>([]);
  const [traces, setTraces] = useState<TraceEntry[]>([]);
  const [execResult, setExecResult] = useState<ExecuteResponse | null>(null);

  const reset = () => {
    setStage("idle");
    setInput("");
    setError(null);
    setIntent(null);
    setPlan(null);
    setAlternatives([]);
    setTraces([]);
    setExecResult(null);
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    setError(null);
    setStage("generating");
    try {
      const res = await api.generate(input.trim());
      setIntent(res.intent);
      setPlan(res.plan);
      setAlternatives(res.alternatives ?? []);
      setTraces(res.traces ?? []);
      setStage("plan_ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
      setStage("idle");
    }
  };

  const handleSelectPlan = (id: string) => {
    const all = plan ? [plan, ...alternatives] : alternatives;
    const found = all.find((p) => p.id === id);
    if (!found) return;
    const others = all.filter((p) => p.id !== id);
    setPlan(found);
    setAlternatives(others);
  };

  const handleRevise = async (text: string) => {
    if (!intent || !plan) return;
    setError(null);
    setStage("revising");
    try {
      const res = await api.revise(text, intent, plan);
      setIntent(res.intent);
      setPlan(res.plan);
      setAlternatives(res.alternatives ?? []);
      setTraces(res.traces ?? []);
      setStage("plan_ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "修改失败");
      setStage("plan_ready");
    }
  };

  const handleExecute = async () => {
    if (!plan || !intent) return;
    setError(null);
    setStage("executing");
    try {
      const res = await api.execute(plan, intent);
      setExecResult(res);
      setTraces((prev) => [...prev, ...(res.traces ?? [])]);
      setStage("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "执行失败");
      setStage("plan_ready");
    }
  };

  const isLoading =
    stage === "generating" || stage === "revising" || stage === "executing";

  return (
    <div className="min-h-screen bg-gray-50">
      {/* header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <span className="text-lg font-bold text-brand-500">NativePlanning</span>
            <span className="ml-2 text-sm text-gray-400">本地生活活动规划</span>
          </div>
          {stage !== "idle" && (
            <button
              onClick={reset}
              className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
            >
              重新开始
            </button>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        {/* input */}
        {stage === "idle" && (
          <div className="space-y-4">
            <div className="text-center py-8">
              <h1 className="text-2xl font-bold text-gray-900">一句话，安排好本地生活</h1>
              <p className="text-gray-500 mt-2">告诉我你想做什么，我帮你搞定时间、地点、餐饮和预订</p>
            </div>
            <form onSubmit={handleGenerate} className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="今天下午带孩子去亲子乐园玩，顺便吃个饭"
                className="flex-1 rounded-lg border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                type="submit"
                disabled={!input.trim()}
                className="px-5 py-3 rounded-lg bg-brand-500 text-white text-sm font-semibold hover:bg-brand-600 transition-colors disabled:opacity-40"
              >
                规划
              </button>
            </form>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_INPUTS.map((s) => (
                <button
                  key={s}
                  onClick={() => setInput(s)}
                  className="text-xs px-3 py-1.5 rounded-full border border-gray-200 text-gray-500 hover:border-brand-300 hover:text-brand-500 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* loading states */}
        {isLoading && (
          <div className="flex flex-col items-center py-16 gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            <p className="text-sm text-gray-500">
              {stage === "generating" && "正在生成方案…"}
              {stage === "revising" && "正在修改方案…"}
              {stage === "executing" && "正在执行预订…"}
            </p>
          </div>
        )}

        {/* error */}
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
            ⚠ {error}
          </div>
        )}

        {/* plan_ready / done */}
        {(stage === "plan_ready" || stage === "done") && intent && plan && (
          <>
            {/* intent */}
            <IntentPanel intent={intent} />

            {/* plan selector if alternatives exist */}
            {alternatives.length > 0 && (
              <PlanSelector
                plans={[plan, ...alternatives]}
                selectedId={plan.id}
                onChange={handleSelectPlan}
              />
            )}

            {/* selected plan detail */}
            <div className="space-y-4">
              <PlanCard plan={plan} />

              {/* timeline */}
              {plan.steps.length > 0 && (
                <div className="rounded-lg border bg-white p-4 shadow-sm space-y-3">
                  <p className="text-sm font-semibold text-gray-500">行程时间线</p>
                  <Timeline steps={plan.steps} />
                </div>
              )}
            </div>

            {/* revision */}
            {stage === "plan_ready" && (
              <div className="rounded-lg border bg-white p-4 shadow-sm space-y-4">
                <RevisionInput onRevise={handleRevise} disabled={false} />
                <div className="flex justify-end">
                  <button
                    onClick={handleExecute}
                    className="px-6 py-2.5 rounded-lg bg-brand-500 text-white text-sm font-semibold hover:bg-brand-600 transition-colors"
                  >
                    确认并执行预订
                  </button>
                </div>
              </div>
            )}

            {/* execution result */}
            {stage === "done" && execResult && (
              <div className="rounded-lg border bg-white p-4 shadow-sm space-y-4">
                <p className="text-sm font-semibold text-gray-500">执行结果</p>
                <ExecutionResult results={execResult.results} />
                {execResult.share_message && (
                  <ShareMessage shareMessage={execResult.share_message} />
                )}
              </div>
            )}

            {/* tool trace */}
            {traces.length > 0 && <ToolTrace traces={traces} />}
          </>
        )}
      </main>
    </div>
  );
}
