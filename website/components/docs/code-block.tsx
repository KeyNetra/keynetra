"use client";

import { Check, Copy } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

function extractCode(children: ReactNode): string {
  if (
    children &&
    typeof children === "object" &&
    "props" in children &&
    typeof children.props === "object" &&
    children.props &&
    "children" in children.props
  ) {
    const value = children.props.children;
    return Array.isArray(value) ? value.join("") : String(value ?? "");
  }
  return String(children ?? "");
}

export function CodeBlock({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const source = extractCode(children).trim();
  const language =
    typeof children === "object" &&
    children &&
    "props" in children &&
    typeof children.props === "object" &&
    children.props &&
    "className" in children.props &&
    typeof children.props.className === "string"
      ? children.props.className.replace("language-", "")
      : "text";

  async function handleCopy() {
    await navigator.clipboard.writeText(source);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="group relative my-8 overflow-hidden rounded-3xl border border-border/60 bg-slate-950 shadow-2xl">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <span className="text-xs uppercase tracking-[0.24em] text-slate-400">
          {language}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300 transition hover:bg-white/10"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className={className}>
        <code className="block overflow-x-auto p-5 text-sm leading-7 text-slate-100">
          {source}
        </code>
      </pre>
    </div>
  );
}
