import type { Metadata } from "next";

import { BlogCard } from "@/components/blog/blog-card";
import { PageHero } from "@/components/marketing/page-hero";
import { getAllPosts, getBlogCategories } from "@/lib/content";
import { slugify } from "@/lib/utils";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Blog",
  description: "Engineering writing on authorization models, policy systems, and platform design."
};

export default function BlogIndexPage() {
  const posts = getAllPosts();
  const categories = getBlogCategories();

  return (
    <main>
      <PageHero
        eyebrow="Blog"
        title="Writing about authorization as infrastructure."
        description="Essays and explainers for backend engineers and platform teams building permission systems that need to survive product growth."
      />
      <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex flex-wrap gap-3">
          {categories.map((category) => (
            <Link
              key={category}
              href={`/blog/category/${slugify(category)}`}
              className="rounded-full border border-border/60 px-4 py-2 text-sm text-muted-foreground transition hover:border-primary/40 hover:text-foreground"
            >
              {category}
            </Link>
          ))}
        </div>
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {posts.map((post) => (
            <BlogCard key={post.slugAsPath} post={post} />
          ))}
        </div>
      </section>
    </main>
  );
}
