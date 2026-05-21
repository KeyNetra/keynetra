"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { languageSnippets } from "@/lib/site-config";
import { cn } from "@/lib/utils";

const languages = [
  { id: "node", label: "Node.js" },
  { id: "go", label: "Go" },
  { id: "python", label: "Python" }
] as const;

function highlightCode(code) {
  // Escape HTML first for safety
  code = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Keywords list (your originals)
  const keywords = 'import|from|const|await|async|package|func|return|if|panic|print';

  // Highlight booleans first
  code = code.replace(/\b(true|false)\b/g, '<span class="text-violet-300">$1</span>');

  // Highlight strings first (single pass, basic escaped quotes support via non-greedy)
  code = code.replace(/"([^"\\]|\\.)*"/g, '<span class="text-emerald-300">$&</span>')
             .replace(/'([^'\\]|\\.)*'/g, '<span class="text-emerald-300">$&</span>');

  // Now keywords (won't match inside already-wrapped strings)
  code = code.replace(new RegExp(`\\b(${keywords})\\b`, 'g'), '<span class="text-sky-300">$1</span>');

  return code;
}

export function CodeTabs() {
  const [active, setActive] = useState<(typeof languages)[number]["id"]>("node");
  const [copied, setCopied] = useState(false);

  const snippet = languageSnippets[active];

  async function handleCopy() {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="overflow-hidden rounded-[28px] border border-[#20385f] bg-[#07101d] shadow-[0_30px_80px_rgba(11,31,58,0.45)]">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 px-5 py-4">
        <div className="flex flex-wrap gap-2">
          {languages.map((language) => (
            <button
              key={language.id}
              type="button"
              onClick={() => setActive(language.id)}
              className={cn(
                "rounded-full px-3 py-1.5 text-sm transition",
                active === language.id
                  ? "bg-white/10 text-white"
                  : "text-slate-400 hover:text-white"
              )}
            >
              {language.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-sm text-slate-300 transition hover:bg-white/10"
        >
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="border-b border-white/10 bg-[#0b1f3a] px-5 py-3 text-sm text-slate-300">
        <span className="text-slate-500">checkAccess</span>
        <span className="mx-2 text-cyan-300">=&gt;</span>
        <span className="rounded-full bg-emerald-400/10 px-2 py-1 text-emerald-300">
          allow / deny
        </span>
      </div>
      <pre className="overflow-x-auto p-5 text-sm leading-7 text-slate-100">
        <code dangerouslySetInnerHTML={{ __html: highlightCode(snippet) }} />
      </pre>
      <div className="grid gap-3 border-t border-white/10 bg-[#081423] px-5 py-4 text-xs text-slate-400 sm:grid-cols-3">
        <p><span className="text-slate-200">Input:</span> user, resource, action</p>
        <p><span className="text-slate-200">Evaluation:</span> roles, policies, relationships</p>
        <p><span className="text-slate-200">Output:</span> allow or deny with traceable metadata</p>
      </div>
    </div>
  );
}
