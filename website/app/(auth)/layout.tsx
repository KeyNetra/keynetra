import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <div className="absolute inset-0 bg-hero-grid bg-[size:42px_42px] opacity-40" />
      <div className="absolute left-1/2 top-0 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-sky-500/15 blur-3xl" />
      <div className="relative flex min-h-screen items-center justify-center px-4 py-16">
        {children}
      </div>
    </div>
  );
}
