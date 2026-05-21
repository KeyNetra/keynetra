import { getAllPosts } from "@/lib/content";
import { siteConfig } from "@/lib/site-config";

export async function GET() {
  const posts = getAllPosts();

  const xml = `<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>${siteConfig.name} Blog</title>
    <link>${siteConfig.domain}/blog</link>
    <description>Engineering writing on authorization infrastructure.</description>
    ${posts
      .map(
        (post) => `
    <item>
      <title>${post.title}</title>
      <link>${siteConfig.domain}/blog/${post.slugAsPath}</link>
      <description>${post.description}</description>
      <pubDate>${new Date(post.publishedAt).toUTCString()}</pubDate>
    </item>`
      )
      .join("")}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8"
    }
  });
}
