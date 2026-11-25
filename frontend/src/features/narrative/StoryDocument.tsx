/**
 * 行旅识景 TripScape / 故事正文渲染
 * 创建日期: 2026-11-25
 *
 * 把 stories/*.md 的正文渲染成可读段落，完成:
 *     1. 标题、小标题、列表、引用四类块的最小解析（不引入 markdown 依赖）
 *     2. 用排版区分「叙述」「时间刻度」「材料出处」，让长文可扫读
 *
 * 依赖:
 *     依赖库: 无（复用项目现有 Tailwind 主题）
 *
 * 用法:
 *     <StoryDocument markdown={story.markdown} />
 *
 * 注意:
 *     1. 只解析本项目生成的故事文档结构，不做通用 Markdown 兼容。
 *     2. 不渲染 HTML，避免把外部文本当结构执行。
 */

import { Fragment } from "react";

type Block =
  | { kind: "h1" | "h2" | "h3" | "quote"; text: string }
  | { kind: "p"; text: string }
  | { kind: "list"; items: string[] };

/** 逐行解析成块；连续列表项合并成一个块，空行只做分块提示 */
function parse(markdown: string): Block[] {
  const blocks: Block[] = [];
  let list: string[] = [];

  const flushList = () => {
    if (list.length) {
      blocks.push({ kind: "list", items: list });
      list = [];
    }
  };

  for (const raw of markdown.split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushList();
      continue;
    }
    if (line.startsWith("### ")) {
      flushList();
      blocks.push({ kind: "h3", text: line.slice(4) });
    } else if (line.startsWith("## ")) {
      flushList();
      blocks.push({ kind: "h2", text: line.slice(3) });
    } else if (line.startsWith("# ")) {
      flushList();
      blocks.push({ kind: "h1", text: line.slice(2) });
    } else if (line.startsWith("- ")) {
      list.push(line.slice(2));
    } else if (line.startsWith("> ")) {
      flushList();
      blocks.push({ kind: "quote", text: line.slice(2) });
    } else {
      flushList();
      blocks.push({ kind: "p", text: line });
    }
  }
  flushList();
  return blocks;
}

export default function StoryDocument({ markdown }: { markdown: string }) {
  const blocks = parse(markdown);

  return (
    <article className="space-y-2.5 text-[12px] leading-[1.75] text-foreground/85">
      {blocks.map((block, index) => {
        if (block.kind === "h1") {
          return (
            <h2 key={index} className="text-[15px] font-bold leading-snug text-foreground">
              {block.text}
            </h2>
          );
        }
        if (block.kind === "h2") {
          return (
            <h3
              key={index}
              className="mt-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-primary"
            >
              <span className="h-1 w-1 rounded-full bg-primary" />
              {block.text}
            </h3>
          );
        }
        if (block.kind === "h3") {
          return (
            <h4 key={index} className="text-[11.5px] font-semibold text-foreground/90">
              {block.text}
            </h4>
          );
        }
        if (block.kind === "list") {
          return (
            <ul key={index} className="space-y-1 pl-0.5">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="flex gap-1.5">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-primary/70" />
                  <span className="min-w-0 flex-1">{item}</span>
                </li>
              ))}
            </ul>
          );
        }
        if (block.kind === "quote") {
          return (
            <blockquote
              key={index}
              className="border-l-2 border-primary/40 pl-2 text-[11px] text-muted-foreground"
            >
              {block.text}
            </blockquote>
          );
        }
        return (
          <Fragment key={index}>
            <p>{block.text}</p>
          </Fragment>
        );
      })}
    </article>
  );
}
