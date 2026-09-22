/**
 * Renders model output as markdown.
 *
 * The models reply in markdown (headings, bold, tables, numbered citations), so
 * showing the raw text made every answer look like a dump of syntax.
 *
 * Raw HTML is deliberately not enabled. react-markdown ignores embedded HTML
 * unless rehype-raw is added, and this text comes from a model summarising pages
 * fetched off the open web, so it is untrusted input. Keeping HTML off means no
 * markup from a search result can reach the DOM.
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import Link from '@cloudscape-design/components/link';

interface MarkdownProps {
  children: string;
}

export default function Markdown({ children }: MarkdownProps) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        // GFM adds the tables, strikethrough and autolinks the models actually use.
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children: label }) => (
            <Link href={href} external externalIconAriaLabel="Opens in a new tab">
              {label}
            </Link>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
