import Link from "next/link";

import { getDocsNavigation } from "@/lib/content";
import { cn } from "@/lib/utils";

export function DocsSidebar({ currentSlug }: { currentSlug: string }) {
  const groups = getDocsNavigation();

  return (
    <aside className="hidden w-72 shrink-0 lg:block">
      <div className="sticky top-24 space-y-8">
        {groups.map(([section, docs]) => (
          <div key={section}>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
              {section}
            </h3>
            <div className="space-y-1">
              {docs.map((doc) => {
                const href = `/docs/${doc.slugAsPath}`;
                const active = doc.slugAsPath === currentSlug;
                return (
                  <Link
                    key={doc.slugAsPath}
                    href={href}
                    className={cn(
                      "block rounded-2xl px-4 py-3 text-sm transition",
                      active
                        ? "bg-primary/10 font-medium text-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    )}
                  >
                    {doc.title}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
