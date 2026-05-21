import { PageHero } from "@/components/marketing/page-hero";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const tiers = [
  {
    name: "Open Source",
    price: "Free",
    points: ["Self-hosted runtime", "Docs and examples", "Community-driven contribution model"]
  },
  {
    name: "Cloud",
    price: "Contact us",
    points: ["Managed control plane", "Operational visibility", "Faster onboarding for product teams"]
  },
  {
    name: "Enterprise",
    price: "Custom",
    points: ["Deployment guidance", "Governance workflows", "Priority support and architecture review"]
  }
];

export default function PricingPage() {
  return (
    <main>
      <PageHero
        eyebrow="Pricing"
        title="Flexible adoption for self-hosted teams and enterprise programs."
        description="Start with the open-source platform, move into managed or enterprise operating models when your authorization surface and governance needs expand."
      />
      <section className="mx-auto grid max-w-6xl gap-6 px-4 py-20 sm:px-6 lg:grid-cols-3 lg:px-8">
        {tiers.map((tier) => (
          <Card key={tier.name} className="p-7">
            <h2 className="text-2xl font-semibold text-foreground">{tier.name}</h2>
            <p className="mt-3 text-3xl font-semibold text-primary">{tier.price}</p>
            <div className="mt-6 space-y-3 text-sm leading-7 text-muted-foreground">
              {tier.points.map((point) => (
                <p key={point}>{point}</p>
              ))}
            </div>
            <Button className="mt-8 w-full">{tier.name === "Open Source" ? "Start Building" : "Talk to Sales"}</Button>
          </Card>
        ))}
      </section>
    </main>
  );
}
