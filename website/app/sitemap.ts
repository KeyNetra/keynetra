import type { MetadataRoute } from "next";

import { getAllDocs, getAllPosts } from "@/lib/content";
import { siteConfig } from "@/lib/site-config";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticRoutes = [
    "",
    "/product",
    "/solutions",
    "/enterprise",
    "/security",
    "/open-source",
    "/pricing",
    "/contact",
    "/docs",
    "/blog",
    "/login",
    "/signup"
  ];

  return [
    ...staticRoutes.map((route) => ({
      url: `${siteConfig.domain}${route}`,
      lastModified: new Date()
    })),
    ...getAllDocs().map((doc) => ({
      url: `${siteConfig.domain}/docs/${doc.slugAsPath}`,
      lastModified: new Date()
    })),
    ...getAllPosts().map((post) => ({
      url: `${siteConfig.domain}/blog/${post.slugAsPath}`,
      lastModified: new Date(post.publishedAt)
    }))
  ];
}
