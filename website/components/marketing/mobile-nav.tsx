"use client";

import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useState } from "react";

import { siteConfig } from "@/lib/site-config";
import { Button } from "@/components/ui/button";

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <div className="md:hidden">
      <button
        type="button"
        aria-label="Open navigation"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-border/70 bg-background/80"
      >
        {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
      </button>
      {open ? (
        <div className="absolute left-4 right-4 top-20 rounded-3xl border border-border/60 bg-background/95 p-5 shadow-2xl backdrop-blur">
          <div className="flex flex-col gap-3">
            {siteConfig.nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-2xl px-4 py-3 text-sm text-muted-foreground transition hover:bg-accent hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
            <div className="mt-2 flex gap-3">
              <Link href="/signup" className="flex-1">
                <Button className="w-full">Get Started</Button>
              </Link>
              <Link href="/docs" className="flex-1">
                <Button variant="secondary" className="w-full">
                  View Docs
                </Button>
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
