import Link from "next/link";

import { Logo } from "@/components/marketing/logo";
import { siteConfig } from "@/lib/site-config";

const footerColumns = [
  {
    title: "Platform",
    links: [
      { href: "/product", label: "Product" },
      { href: "/pricing", label: "Pricing" },
      { href: "/enterprise", label: "Enterprise" }
    ]
  },
  {
    title: "Developers",
    links: [
      { href: "/docs", label: "Docs" },
      { href: "/blog", label: "Blog" },
      { href: "/open-source", label: "Open Source" }
    ]
  },
  {
    title: "Trust",
    links: [
      { href: "/security", label: "Security" },
      { href: "/contact", label: "Contact" },
      { href: siteConfig.githubUrl, label: "GitHub" }
    ]
  }
];

export function SiteFooter() {
  return (
    <footer className="border-t border-border/40 bg-background">
      <div className="mx-auto grid max-w-7xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.2fr,2fr] lg:px-8">
        <div className="space-y-5">
          <Logo />
          <p className="max-w-md text-sm leading-7 text-muted-foreground">
            Authorization infrastructure for teams that need one decision system
            across APIs, services, workers, and internal tools.
          </p>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            {siteConfig.slogan}
          </p>
        </div>
        <div className="grid gap-10 sm:grid-cols-3">
          {footerColumns.map((column) => (
            <div key={column.title}>
              <h3 className="text-sm font-semibold text-foreground">{column.title}</h3>
              <div className="mt-4 flex flex-col gap-3">
                {column.links.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="text-sm text-muted-foreground transition hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </footer>
  );
}
