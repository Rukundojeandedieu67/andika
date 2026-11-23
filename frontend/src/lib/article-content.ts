function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
}

function inline(value: string): string {
  let html = escapeHtml(value)
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>")
  html = html.replace(
    /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g,
    '<img alt="$1" src="$2" />',
  )
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" rel="noreferrer">$1</a>',
  )
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  html = html.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
  return html
}

export function articleHtml(source: string): string {
  const lines = source.replaceAll("\r\n", "\n").split("\n")
  const blocks: string[] = []
  let paragraph: string[] = []
  let list: string[] = []
  let listKind: "ul" | "ol" | null = null
  let code: string[] | null = null

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${inline(paragraph.join(" "))}</p>`)
      paragraph = []
    }
  }
  const flushList = () => {
    if (listKind && list.length) {
      blocks.push(`<${listKind}>${list.join("")}</${listKind}>`)
    }
    list = []
    listKind = null
  }

  for (const line of lines) {
    if (code) {
      if (line.trim() === "```") {
        blocks.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`)
        code = null
      } else {
        code.push(line)
      }
      continue
    }
    if (line.trim() === "```") {
      flushParagraph()
      flushList()
      code = []
      continue
    }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line)
    if (heading?.[1] && heading[2]) {
      flushParagraph()
      flushList()
      const level = Math.min(heading[1].length + 1, 3)
      blocks.push(`<h${level}>${inline(heading[2])}</h${level}>`)
      continue
    }
    if (line.startsWith("> ")) {
      flushParagraph()
      flushList()
      blocks.push(`<blockquote><p>${inline(line.slice(2))}</p></blockquote>`)
      continue
    }
    const bullet = /^[-*]\s+(.+)$/.exec(line)
    const ordered = /^\d+\.\s+(.+)$/.exec(line)
    if (bullet?.[1] || ordered?.[1]) {
      flushParagraph()
      const kind = bullet ? "ul" : "ol"
      if (listKind && listKind !== kind) flushList()
      listKind = kind
      list.push(`<li>${inline((bullet?.[1] || ordered?.[1]) ?? "")}</li>`)
      continue
    }
    if (line.trim() === "") {
      flushParagraph()
      flushList()
      continue
    }
    flushList()
    paragraph.push(line.trim())
  }
  if (code) blocks.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`)
  flushParagraph()
  flushList()
  return blocks.join("")
}
