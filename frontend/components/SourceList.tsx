import { Source } from "@/lib/types";

export default function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <ul className="sources">
      {sources.map((s, i) => (
        <li key={i}>
          {s.url ? (
            <a href={s.url} target="_blank" rel="noopener noreferrer">
              {s.title || s.url}
            </a>
          ) : (
            <span>{s.title}</span>
          )}
          {s.published_date ? <span className="muted"> ({s.published_date.slice(0, 10)})</span> : null}
          {s.quote ? <div className="quote">&ldquo;{s.quote}&rdquo;</div> : null}
        </li>
      ))}
    </ul>
  );
}
