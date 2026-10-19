import { FieldData } from "@/lib/types";
import SourceList from "./SourceList";
import StatusBadge from "./StatusBadge";

function renderValue(v: any) {
  if (v === null || v === undefined || v === "") return <span className="muted">No value</span>;
  if (typeof v === "string") return <p className="value">{v}</p>;
  if (Array.isArray(v)) {
    return (
      <ul className="plain">
        {v.map((x, i) => (
          <li key={i}>{typeof x === "string" ? x : Object.entries(x).filter(([, val]) => val).map(([k, val]) => `${k}: ${val}`).join(" | ")}</li>
        ))}
      </ul>
    );
  }
  return <p className="value">{Object.entries(v).filter(([, val]) => val).map(([k, val]) => `${k}: ${val}`).join(" | ")}</p>;
}

export default function FieldCard({ label, field }: { label: string; field: FieldData }) {
  return (
    <section className="card">
      <header>
        <h3>{label}</h3>
        <StatusBadge status={field.status} />
      </header>
      {renderValue(field.value)}
      {field.note ? <p className="note">{field.note}</p> : null}
      <SourceList sources={field.sources} />
    </section>
  );
}
