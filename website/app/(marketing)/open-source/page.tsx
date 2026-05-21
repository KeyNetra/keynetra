import Link from "next/link";

import { PageHero } from "@/components/marketing/page-hero";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { siteConfig } from "@/lib/site-config";

export default function OpenSourcePage() {
  return (
    <main>
      <PageHero
        eyebrow="Open Source"
        title="Open source because authorization infrastructure benefits from inspection."
        description="KeyNetra is built in the open so teams can evaluate the architecture, contribute to the direction, and operate the platform without vendor lock-in."
      />
      <section className="mx-auto grid max-w-6xl gap-6 px-4 py-20 sm:px-6 lg:grid-cols-3 lg:px-8">
        <Card className="p-7">
          <h2 className="text-2xl font-semibold text-foreground">Why open source</h2>
          <p className="mt-4 text-sm leading-7 text-muted-foreground">
            Authorization systems sit on critical paths. Teams should be able to inspect how
            decisions are made and how the system is operated.
          </p>
        </Card>
        <Card className="p-7">
          <h2 className="text-2xl font-semibold text-foreground">Contribution path</h2>
          <p className="mt-4 text-sm leading-7 text-muted-foreground">
            Contribute docs, policy examples, SDK improvements, testing workflows, or runtime
            hardening with a clear GitHub-based workflow.
          </p>
        </Card>
        <Card className="p-7">
          <h2 className="text-2xl font-semibold text-foreground">Developer trust</h2>
          <p className="mt-4 text-sm leading-7 text-muted-foreground">
            Open APIs, visible contracts, and local self-hosting make adoption easier for
            platform teams with strict evaluation standards.
          </p>
        </Card>
      </section>
      <section className="mx-auto max-w-5xl px-4 pb-24 sm:px-6 lg:px-8">
        <Card className="flex flex-col items-start justify-between gap-6 p-8 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-3xl font-semibold text-foreground">Star us on GitHub</h2>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              Follow releases, review the code, and contribute to the roadmap.
            </p>
          </div>
          <Link href={siteConfig.githubUrl}>
            <Button size="lg">View Repository</Button>
          </Link>
        </Card>
      </section>
    </main>
  );
}
