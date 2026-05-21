import * as React from "react";

import { cn } from "@/lib/utils";

export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-3xl border border-border/70 bg-card/82 shadow-[0_18px_50px_rgba(11,31,58,0.07)] backdrop-blur-sm",
        className
      )}
      {...props}
    />
  );
}
