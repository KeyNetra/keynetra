import { PageHero } from "@/components/marketing/page-hero";
import { Card } from "@/components/ui/card";

const solutions = [
  ["SaaS platforms", "Support tenant-aware policy, delegated administration, shared workspaces, and subscription-driven entitlements."],
  ["B2B marketplaces", "Model buyers, sellers, operators, and partner relationships without exploding role count."],
  ["Fintech systems", "Enforce approvals, separation of duties, and explicit audit trails for sensitive workflows."],
  ["Internal platforms", "Give platform teams a consistent authorization interface across internal services and tools."]
];

export default function SolutionsPage() {
  return (
    <main>
      <PageHero
        eyebrow="Solutions"
        title="Authorization patterns for teams operating real products."
        description="KeyNetra supports the access models that appear in collaborative SaaS, regulated systems, multi-tenant APIs, and internal platforms."
      />
      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="grid gap-6 md:grid-cols-2">
          {solutions.map(([title, description]) => (
            <Card key={title} className="p-7">
              <h2 className="text-2xl font-semibold text-foreground">{title}</h2>
              <p className="mt-4 text-sm leading-7 text-muted-foreground">{description}</p>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}
