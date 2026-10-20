import { isValidElement, memo, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy } from "lucide-react";
import "highlight.js/styles/github.css";

function nodeToText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join("");
  if (isValidElement(node)) {
    return nodeToText((node.props as { children?: ReactNode }).children);
  }
  return "";
}

interface MdastNode {
  type: string;
  value?: string;
  url?: string;
  children?: MdastNode[];
}

const CITATION_RE = /\[(\d+)\]/g;

function splitCitations(value: string): MdastNode[] {
  const nodes: MdastNode[] = [];
  let last = 0;
  for (const match of value.matchAll(CITATION_RE)) {
    const index = match.index ?? 0;
    if (index > last) nodes.push({ type: "text", value: value.slice(last, index) });
    nodes.push({
      type: "link",
      url: `#source-${match[1]}`,
      children: [{ type: "text", value: match[0] }],
    });
    last = index + match[0].length;
  }
  if (last < value.length) nodes.push({ type: "text", value: value.slice(last) });
  return nodes;
}

function visitCitations(node: MdastNode): void {
  if (!node.children) return;
  const next: MdastNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && child.value && CITATION_RE.test(child.value)) {
      CITATION_RE.lastIndex = 0;
      next.push(...splitCitations(child.value));
    } else {
      next.push(child);
    }
    if (child.type !== "text") visitCitations(child);
  }
  node.children = next;
}

function remarkCitations() {
  return (tree: MdastNode) => {
    visitCitations(tree);
  };
}

function scrollToSource(element: HTMLElement, index: string): void {
  const message = element.closest(".message");
  const card = message?.querySelector<HTMLElement>(`.source-card[data-index="${index}"]`);
  if (!card) return;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.classList.add("flash");
  window.setTimeout(() => card.classList.remove("flash"), 1200);
}

function useCopy() {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = (text: string) => {
    void navigator.clipboard.writeText(text);
    setCopied(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), 1500);
  };

  return { copied, copy };
}

function CodeBlock({ className, children }: { className?: string; children: ReactNode }) {
  const { copied, copy } = useCopy();
  const language = /language-(\w+)/.exec(className ?? "")?.[1] ?? "code";
  const raw = nodeToText(children).replace(/\n$/, "");

  return (
    <div className="code-block">
      <div className="code-head">
        <span className="code-lang">{language}</span>
        <button className="code-copy" onClick={() => copy(raw)}>
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? "Скопировано" : "Копировать"}
        </button>
      </div>
      <pre className={className}>{children}</pre>
    </div>
  );
}

export const Markdown = memo(function Markdown({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkCitations]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre({ children }) {
            const child = Array.isArray(children) ? children[0] : children;
            const className = isValidElement(child)
              ? (child.props as { className?: string }).className
              : undefined;
            return <CodeBlock className={className}>{children}</CodeBlock>;
          },
          a({ href, children }) {
            if (href?.startsWith("#source-")) {
              const index = href.slice("#source-".length);
              return (
                <button
                  type="button"
                  className="citation"
                  title={`Источник ${index}`}
                  onClick={(event) => scrollToSource(event.currentTarget, index)}
                >
                  {children}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer noopener">
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});

export function CopyMessageButton({ text }: { text: string }) {
  const { copied, copy } = useCopy();
  return (
    <button className="message-copy" onClick={() => copy(text)} title="Скопировать сообщение">
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? "Скопировано" : "Копировать"}
    </button>
  );
}
