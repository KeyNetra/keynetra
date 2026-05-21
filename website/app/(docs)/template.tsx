import type { ReactNode } from "react";

import { PageTransition } from "@/components/marketing/page-transition";

export default function DocsTemplate({ children }: { children: ReactNode }) {
  return <PageTransition>{children}</PageTransition>;
}
