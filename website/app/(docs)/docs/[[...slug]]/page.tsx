import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DocsSidebar } from "@/components/docs/docs-sidebar";
import { DocsToc } from "@/components/docs/docs-toc";
import { DocsTopbar } from "@/components/docs/docs-topbar";
import { getAllDocs, getDocBySlug, renderMdx } from "@/lib/content";

type PageProps = {
  params: Promise<{ slug?: string[] }>;
};

export async function generateStaticParams() {
  return getAllDocs().map((doc) => ({ slug: doc.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const resolved = await params;
  const slug = resolved.slug ?? ["getting-started", "introduction"];
  const doc = getDocBySlug(slug);
  if (!doc) {
    return {};
  }
  return {
    title: doc.title,
    description: doc.description
  };
}

export default async function DocsCatchAllPage({ params }: PageProps) {
  const resolved = await params;
  const slug = resolved.slug ?? ["getting-started", "introduction"];
  const doc = getDocBySlug(slug);

  if (!doc) {
    notFound();
  }

  const content = await renderMdx(doc.body);

  return (
    <main>
      <DocsTopbar />
      <div className="mx-auto flex max-w-7xl gap-10 px-4 py-10 sm:px-6 lg:px-8">
        <DocsSidebar currentSlug={doc.slugAsPath} />
        <article className="min-w-0 flex-1">
          <div className="mb-8 border-b border-border/50 pb-8">
            <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
              {doc.section}
            </p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight text-foreground">
              {doc.title}
            </h1>
            <p className="mt-4 max-w-3xl text-lg leading-8 text-muted-foreground">
              {doc.description}
            </p>
          </div>
          <div className="prose prose-lg max-w-none">{content}</div>
        </article>
        <DocsToc items={doc.toc} />
      </div>
    </main>
  );
}
