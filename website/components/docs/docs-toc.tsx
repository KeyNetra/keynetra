import Link from "next/link";

import type { TocItem } from "@/lib/content";
import { cn } from "@/lib/utils";

export function DocsToc({ items }: { items: TocItem[] }) {
  if (!items.length) {
    return null;
  }

  return (
    <aside className="hidden w-64 xl:block">
      <div className="sticky top-24 rounded-3xl border border-border/60 bg-card/70 p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
          On this page
        </p>
        <div className="mt-4 space-y-2">
          {items.map((item) => (
            <Link
              key={item.id}
              href={`#${item.id}`}
              className={cn(
                "block text-sm text-muted-foreground transition hover:text-foreground",
                item.level === 3 && "pl-4 text-xs"
              )}
            >
              {item.text}
            </Link>
          ))}
        </div>
      </div>
    </aside>
  );
}
