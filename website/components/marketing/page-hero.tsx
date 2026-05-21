import { Badge } from "@/components/ui/badge";

export function PageHero({
  eyebrow,
  title,
  description
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <section className="border-b border-border/40">
      <div className="mx-auto max-w-5xl px-4 py-20 sm:px-6 lg:px-8">
        <Badge>{eyebrow}</Badge>
        <h1 className="mt-6 max-w-3xl text-5xl font-semibold tracking-tight text-foreground sm:text-6xl">
          {title}
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground">
          {description}
        </p>
      </div>
    </section>
  );
}
