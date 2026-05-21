import Link from "next/link";
import { format } from "date-fns";

import type { BlogEntry } from "@/lib/content";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function BlogCard({ post }: { post: BlogEntry }) {
  return (
    <Card className="h-full p-6 transition hover:-translate-y-1 hover:border-primary/40">
      <div className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-muted-foreground">
        <Badge>{post.category}</Badge>
        <span>{post.readingTime}</span>
      </div>
      <div className="mt-5">
        <Link href={`/blog/${post.slugAsPath}`} className="group">
          <h3 className="text-2xl font-semibold tracking-tight text-foreground transition group-hover:text-primary">
            {post.title}
          </h3>
        </Link>
        <p className="mt-3 text-sm leading-7 text-muted-foreground">{post.description}</p>
      </div>
      <div className="mt-6 flex flex-wrap gap-2">
        {post.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-accent px-3 py-1 text-xs text-muted-foreground"
          >
            {tag}
          </span>
        ))}
      </div>
      <div className="mt-6 text-sm text-muted-foreground">
        {post.author} • {format(new Date(post.publishedAt), "MMMM d, yyyy")}
      </div>
    </Card>
  );
}
