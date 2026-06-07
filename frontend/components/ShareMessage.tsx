"use client";

import { useState } from "react";
import type { ShareMessage as ShareMsg } from "@/lib/types";

interface Props {
  shareMessage: ShareMsg;
}

export default function ShareMessage({ shareMessage }: Props) {
  const [copied, setCopied] = useState(false);

  const text = shareMessage.message ?? "";

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-gray-500">分享消息</p>
        <button
          onClick={handleCopy}
          className="text-xs px-3 py-1 rounded-full border border-brand-500 text-brand-500 hover:bg-brand-50 transition-colors"
        >
          {copied ? "已复制 ✓" : "复制"}
        </button>
      </div>
      <textarea
        readOnly
        value={text}
        rows={6}
        className="w-full rounded-lg border border-gray-200 p-3 text-sm text-gray-700 bg-gray-50 resize-none focus:outline-none"
      />
    </div>
  );
}
