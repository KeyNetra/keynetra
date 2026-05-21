import { notFound } from "next/navigation";

import { BlogCard } from "@/components/blog/blog-card";
import { PageHero } from "@/components/marketing/page-hero";
import { getBlogCategories, getPostsByCategory } from "@/lib/content";
import { slugify } from "@/lib/utils";

type PageProps = {
  params: Promise<{ category: string }>;
};

export async function generateStaticParams() {
  return getBlogCategories().map((category) => ({
    category: slugify(category)
  }));
}

export default async function BlogCategoryPage({ params }: PageProps) {
  const { category } = await params;
  const posts = getPostsByCategory(category);
  if (!posts.length) {
    notFound();
  }

  return (
    <main>
      <PageHero
        eyebrow="Category"
        title={posts[0].category}
        description={`Posts tagged under ${posts[0].category.toLowerCase()} for engineers working on authorization systems.`}
      />
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid gap-6 md:grid-cols-2">
          {posts.map((post) => (
            <BlogCard key={post.slugAsPath} post={post} />
          ))}
        </div>
      </section>
    </main>
  );
}
