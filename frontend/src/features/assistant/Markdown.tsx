import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const STYLES = [
  "space-y-2 text-sm leading-relaxed",
  "[&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:font-semibold",
  "[&_ol]:list-decimal [&_ol]:pl-5 [&_ul]:list-disc [&_ul]:pl-5 [&_li]:my-0.5",
  "[&_table]:w-full [&_table]:text-xs [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1",
  "[&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-2 [&_th]:py-1 [&_th]:text-left",
  "[&_code]:rounded [&_code]:bg-muted [&_code]:px-1",
].join(" ");

export function Markdown({ text }: { text: string }) {
  return (
    <div className={STYLES}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline">{children}</a>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
