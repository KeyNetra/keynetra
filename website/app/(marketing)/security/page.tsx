import { PageHero } from "@/components/marketing/page-hero";
import { Card } from "@/components/ui/card";

export default function SecurityPage() {
  return (
    <main>
      <PageHero
        eyebrow="Security"
        title="Security posture designed for authorization-critical systems."
        description="KeyNetra is designed to support strict tenant boundaries, auditable decisioning, and operational controls that security-conscious teams expect from infrastructure software."
      />
      <section className="mx-auto grid max-w-6xl gap-6 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:px-8">
        {[
          ["Tenant isolation", "Support tenant-aware routing and strict tenancy controls so authorization state stays scoped correctly."],
          ["Auditability", "Capture access decisions and administrative changes with request correlation for incident review."],
          ["Operational hardening", "Use rate limiting, readiness checks, structured logs, and metrics to support secure operation."],
          ["Compliance-ready tone", "SOC 2 style expectations start with traceability, reviewability, and predictable change management."]
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
