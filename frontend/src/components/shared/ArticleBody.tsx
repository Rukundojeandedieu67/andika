import { articleHtml } from "@/lib/article-content"

export function ArticleBody({ content }: { content: string }) {
  return (
    <div
      className="prose-article"
      dangerouslySetInnerHTML={{ __html: articleHtml(content) }}
    />
  )
}
