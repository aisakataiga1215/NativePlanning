"use client";

import { useState } from "react";

interface Props {
  onRevise: (text: string) => void;
  disabled: boolean;
}

export default function RevisionInput({ onRevise, disabled }: Props) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    onRevise(trimmed);
    setValue("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={disabled}
        placeholder="输入修改意见，例如：换个餐厅、改到下午…"
        className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:bg-gray-50 disabled:text-gray-400"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
      >
        修改方案
      </button>
    </form>
  );
}
