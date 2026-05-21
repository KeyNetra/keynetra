import { Mail, MessageSquareText, Shield } from "lucide-react";

import { PageHero } from "@/components/marketing/page-hero";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function ContactPage() {
  return (
    <main>
      <PageHero
        eyebrow="Contact"
        title="Talk to the team building KeyNetra."
        description="Use this page for product questions, enterprise deployment conversations, or open-source collaboration opportunities."
      />
      <section className="mx-auto grid max-w-6xl gap-8 px-4 py-20 sm:px-6 lg:grid-cols-[0.9fr,1.1fr] lg:px-8">
        <div className="space-y-4">
          {[
            [Mail, "General inquiries", "product@keynetra.dev"],
            [MessageSquareText, "Partnerships", "partners@keynetra.dev"],
            [Shield, "Security disclosures", "security@keynetra.dev"]
          ].map(([Icon, title, value]) => (
            <Card key={title as string} className="flex items-center gap-4 p-6">
              <div className="rounded-2xl bg-primary/10 p-3 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium text-foreground">{title as string}</p>
                <p className="text-sm text-muted-foreground">{value as string}</p>
              </div>
            </Card>
          ))}
        </div>
        <Card className="p-7">
          <div className="grid gap-4 sm:grid-cols-2">
            <Input placeholder="Name" />
            <Input placeholder="Work email" />
          </div>
          <Input className="mt-4" placeholder="Company" />
          <textarea
            className="mt-4 min-h-40 w-full rounded-3xl border border-border/70 bg-background/80 p-4 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            placeholder="Tell us what you're building and where authorization is becoming difficult."
          />
          <Button className="mt-6">Send message</Button>
        </Card>
      </section>
    </main>
  );
}
