import type { Metadata } from "next";
import { format } from "date-fns";
import { notFound } from "next/navigation";

import { getAllPosts, getPostBySlug, renderMdx } from "@/lib/content";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: post.slugAsPath }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) {
    return {};
  }
  return {
    title: post.title,
    description: post.description
  };
}

export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) {
    notFound();
  }

  const content = await renderMdx(post.body);

  return (
    <main className="mx-auto max-w-4xl px-4 py-20 sm:px-6 lg:px-8">
      <div className="border-b border-border/50 pb-8">
        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
          {post.category}
        </p>
        <h1 className="mt-4 text-5xl font-semibold tracking-tight text-foreground">
          {post.title}
        </h1>
        <p className="mt-6 text-lg leading-8 text-muted-foreground">{post.description}</p>
        <div className="mt-6 text-sm text-muted-foreground">
          {post.author} • {format(new Date(post.publishedAt), "MMMM d, yyyy")} •{" "}
          {post.readingTime}
        </div>
      </div>
      <article className="prose prose-lg mt-10 max-w-none">{content}</article>
    </main>
  );
}
