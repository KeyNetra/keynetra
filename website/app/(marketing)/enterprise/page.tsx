import { PageHero } from "@/components/marketing/page-hero";
import { Card } from "@/components/ui/card";

export default function EnterprisePage() {
  return (
    <main>
      <PageHero
        eyebrow="Enterprise"
        title="Built for teams that need authorization infrastructure they can scale and govern."
        description="KeyNetra supports production deployment patterns that matter to larger organizations: high availability, auditability, operational consistency, and policy control with clear blast-radius management."
      />
      <section className="mx-auto grid max-w-6xl gap-6 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:px-8">
        {[
          ["Scalability", "Horizontal API scaling, cache-aware decision paths, and deployment assets for containerized environments."],
          ["High availability", "Run KeyNetra behind managed ingress with durable data stores, readiness probes, and safe rollout workflows."],
          ["Multi-region readiness", "Keep policy and access checks close to application traffic while maintaining operational control."],
          ["Audit and governance", "Inspect decision traces, revisions, and change history for security and compliance stakeholders."]
        ].map(([title, description]) => (
          <Card key={title} className="p-7">
            <h2 className="text-2xl font-semibold text-foreground">{title}</h2>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">{description}</p>
          </Card>
        ))}
      </section>
    </main>
  );
}
