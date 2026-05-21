import Link from "next/link";
import type {
  AnchorHTMLAttributes,
  BlockquoteHTMLAttributes,
  TableHTMLAttributes,
  TdHTMLAttributes,
  ThHTMLAttributes
} from "react";

import { CodeBlock } from "@/components/docs/code-block";
import { cn } from "@/lib/utils";

export const mdxComponents = {
  pre: CodeBlock,
  a: ({
    href = "",
    className,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement>) => {
    const classes = cn("font-medium text-primary underline underline-offset-4", className);
    if (href.startsWith("/")) {
      return <Link href={href} className={classes} {...props} />;
    }
    return (
      <a
        href={href}
        className={classes}
        target="_blank"
        rel="noreferrer"
        {...props}
      />
    );
  },
  table: (props: TableHTMLAttributes<HTMLTableElement>) => (
    <div className="my-8 overflow-x-auto">
      <table className="w-full text-left text-sm" {...props} />
    </div>
  ),
  th: (props: ThHTMLAttributes<HTMLTableCellElement>) => (
    <th className="border-b border-border px-4 py-3 font-medium text-foreground" {...props} />
  ),
  td: (props: TdHTMLAttributes<HTMLTableCellElement>) => (
    <td className="border-b border-border/60 px-4 py-3 text-muted-foreground" {...props} />
  ),
  blockquote: (props: BlockquoteHTMLAttributes<HTMLQuoteElement>) => (
    <blockquote
      className="my-8 rounded-r-2xl border-l-4 border-primary/60 bg-primary/5 px-6 py-4 text-foreground"
      {...props}
    />
  )
};
