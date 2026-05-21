import { PageHero } from "@/components/marketing/page-hero";
import { Card } from "@/components/ui/card";

export default function ProductPage() {
  return (
    <main>
      <PageHero
        eyebrow="Product"
        title="A centralized decision plane for modern authorization."
        description="KeyNetra brings policy evaluation, relationship resolution, role management, and auditability into one infrastructure layer that backend teams can actually operate."
      />
      <section className="mx-auto grid max-w-6xl gap-6 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:px-8">
        {[
          ["Control plane", "Centralize permission logic instead of scattering checks across services and handlers."],
          ["Policy lifecycle", "Validate, simulate, and roll out changes with less operational risk."],
          ["Deterministic decisions", "Return explainable allow or deny results with trace metadata."],
          ["Multi-language SDKs", "Integrate quickly from Node.js, Go, and Python services."]
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
