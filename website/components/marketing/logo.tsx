import Link from "next/link";

export function Logo() {
  return (
    <Link href="/" className="inline-flex items-center gap-3">
      <span className="relative flex h-10 w-10 items-center justify-center rounded-2xl border border-sky-400/30 bg-sky-500/10 shadow-glow">
        <span className="absolute inset-1 rounded-[14px] border border-white/10" />
        <span className="text-sm font-semibold tracking-[0.3em] text-sky-300">KN</span>
      </span>
      <span className="flex flex-col">
        <span className="text-sm font-semibold tracking-[0.24em] text-foreground">
          KEYNETRA
        </span>
        <span className="text-xs text-muted-foreground">
          Authorization Infrastructure Layer
        </span>
      </span>
    </Link>
  );
}
