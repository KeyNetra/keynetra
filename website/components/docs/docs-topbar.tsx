import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";

export function DocsTopbar() {
  return (
    <div className="sticky top-[73px] z-40 border-b border-border/50 bg-background/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <div>
          <p className="text-sm font-medium text-foreground">Documentation</p>
          <p className="text-xs text-muted-foreground">
            API-first authorization for RBAC, ReBAC, ACL, and policy evaluation.
          </p>
        </div>
        <div className="relative hidden w-full max-w-sm md:block">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-10" placeholder="Search docs" />
        </div>
      </div>
    </div>
  );
}
