import { Link } from "react-router"
import { displayName, formatDate, readingLabel } from "@/lib/format"
import { preferredVariant, resolveMediaUrl } from "@/lib/media-url"
import type { ArticleCard as ArticleCardData, PostRead } from "@/types/api"

export function ArticleCardView({ article }: { article: ArticleCardData | PostRead }) {
  const image =
    "featured_image_media" in article
      ? preferredVariant(article.featured_image_media?.variants) || resolveMediaUrl(article.featured_image)
      : resolveMediaUrl(article.featured_image)
  const views = "view_count" in article ? article.view_count : null
  return (
    <article className="group grid gap-4">
      {image ? (
        <Link to={`/articles/${article.slug}`} className="overflow-hidden rounded-3xl">
          <img
            src={image}
            alt=""
            className="h-52 w-full object-cover transition duration-300 group-hover:scale-[1.02]"
          />
        </Link>
      ) : (
        <div className="h-2 rounded-full bg-brand/30" />
      )}
      <div>
        <p className="text-xs tracking-[0.16em] text-accent uppercase">
          {article.category?.name || ("publication" in article && article.publication?.name) || "Essay"}
        </p>
        <h3 className="mt-2 font-display text-2xl leading-tight">
          <Link to={`/articles/${article.slug}`} className="hover:text-brand">
            {article.title}
          </Link>
        </h3>
        {article.excerpt ? <p className="mt-2 text-ink-soft">{article.excerpt}</p> : null}
        <p className="mt-3 text-sm text-ink-soft">
          <Link to={`/authors/${article.author.username}`} className="text-ink hover:text-brand">
            {displayName(article.author)}
          </Link>
          {" · "}
          {formatDate(article.published_at)}
          {" · "}
          {readingLabel(article.reading_time)}
          {views !== null ? ` · ${views} recorded views` : ""}
        </p>
      </div>
    </article>
  )
}
