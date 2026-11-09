import { memo, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
  markdown: string;
  onCite?: (label: string) => void;
}


export const MarkdownView = memo(function MarkdownView({
  markdown,
  onCite,
}: Props) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }): ReactNode => {
            if (href?.startsWith('#src-')) {
              const label = href.slice(5);
              return (
                <a
                  className="cite"
                  href={href}
                  onClick={(e) => {
                    e.preventDefault();
                    onCite?.(label);
                  }}
                >
                  {children}
                </a>
              );
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
});
