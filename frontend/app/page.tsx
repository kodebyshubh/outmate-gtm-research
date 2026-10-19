"use client";
import { useRef, useState } from "react";
import FieldCard from "@/components/FieldCard";
import RawJson from "@/components/RawJson";
import WarningsBanner from "@/components/WarningsBanner";
import { runResearch } from "@/lib/api";
import { FieldData, Report } from "@/lib/types";

export default function Home() {
  const [name, setName] = useState("");
  const [site, setSite] = useState("");
  const [objective, setObjective] = useState("");
  const [refresh, setRefresh] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const abort = useRef<AbortController | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim() && !site.trim()) {
      setError("Enter a company name or a website.");
      return;
    }
    abort.current = new AbortController();
    setLoading(true);
    setReport(null);
    try {
      setReport(await runResearch({ company_name: name.trim() || undefined, website: site.trim() || undefined, objective: objective.trim() || undefined, refresh }, abort.current.signal));
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  const single: [string, FieldData][] = report
    ? [
        ["Company name", report.company_name],
        ["Website / domain", report.website_domain],
        ["Description", report.company_description],
        ["Industry", report.industry],
        ["Target market", report.target_market],
        ["Employee size", report.employee_size],
        ["Potential GTM opportunity", report.potential_gtm_opportunity],
        ["Contact information", report.contact_information],
      ]
    : [];
  const missing = single.filter(([, f]) => f.status === "unavailable").map(([l]) => l);

  return (
    <main>
      <h1>Company Research Engine</h1>
      <p className="muted">Enter a company and get a source-backed GTM report. Every field says how much to trust it.</p>

      <form onSubmit={submit} className="form">
        <label>
          Company name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Acme AI" />
        </label>
        <label>
          Website or domain
          <input value={site} onChange={(e) => setSite(e.target.value)} placeholder="e.g. https://example.com" />
        </label>
        <label>
          Research objective (optional)
          <textarea value={objective} onChange={(e) => setObjective(e.target.value)} maxLength={500} rows={2} placeholder="Evaluate whether this company could be a good prospect for a B2B GTM service." />
        </label>
        <label className="check">
          <input type="checkbox" checked={refresh} onChange={(e) => setRefresh(e.target.checked)} />
          Fetch fresh data (skip the 15 minute cache)
        </label>
        <div className="actions">
          <button type="submit" disabled={loading}>{loading ? "Researching..." : "Run research"}</button>
          {loading ? <button type="button" onClick={() => abort.current?.abort()}>Cancel</button> : null}
        </div>
      </form>

      {error ? <div className="error" role="alert">{error}</div> : null}

      {report ? (
        <div className="report">
          <WarningsBanner warnings={report.warnings} providers={report.providers} />
          <p className="muted" data-testid="run-summary">
            Run summary: {report.source_urls.length} sources
            {report.providers.map((p) => ` | ${p.name}: ${p.state}${p.message ? " (" + p.message + ")" : ""}`).join("")}
          </p>
          {missing.length ? (
            <aside className="missing"><strong>Missing or uncertain:</strong> {missing.join(", ")}</aside>
          ) : null}
          <div className="grid">
            {single.map(([label, f]) => <FieldCard key={label} label={label} field={f} />)}
          </div>

          <h2>Recent growth signals</h2>
          {report.recent_growth_signals.length ? report.recent_growth_signals.map((f, i) => <FieldCard key={i} label={`Signal ${i + 1}`} field={f} />) : <p className="muted">No supported growth signals found.</p>}

          <h2>Decision-makers</h2>
          {report.decision_makers.length ? report.decision_makers.map((f, i) => <FieldCard key={i} label={`Person ${i + 1}`} field={f} />) : <p className="muted">None found. Names are shown only when a source or provider returns them.</p>}

          {report.mock_enrichment ? (
            <section className="card mock">
              <h3>{report.mock_enrichment.label}</h3>
              <p className="muted">Sample structure only. Not used in any field above.</p>
              <pre>{JSON.stringify({ people: report.mock_enrichment.people, company: report.mock_enrichment.company }, null, 2)}</pre>
            </section>
          ) : null}

          {report.dropped_claims.length ? (
            <details className="dropped">
              <summary>{report.dropped_claims.length} claim(s) rejected by the quote check</summary>
              <ul className="plain">
                {report.dropped_claims.map((d, i) => (
                  <li key={i}>
                    <strong>{d.field}</strong>: {typeof d.claimed_value === "string" ? d.claimed_value : JSON.stringify(d.claimed_value)} <span className="muted">({d.reason})</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          <h2>Sources</h2>
          <ul className="sources">
            {report.source_urls.map((u) => <li key={u}><a href={u} target="_blank" rel="noopener noreferrer">{u}</a></li>)}
          </ul>
          <RawJson data={report} />
        </div>
      ) : null}
    </main>
  );
}
