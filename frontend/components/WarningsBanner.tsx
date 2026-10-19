import { ProviderStatus } from "@/lib/types";

export default function WarningsBanner({ warnings, providers }: { warnings: string[]; providers: ProviderStatus[] }) {
  const bad = providers.filter((p) => p.state === "error" || p.state === "mock" || p.state === "skipped");
  if (!warnings.length && !bad.length) return null;
  return (
    <aside className="banner" role="status">
      <strong>Heads up</strong>
      <ul className="plain">
        {bad.map((p) => (
          <li key={p.name}>
            {p.name}: {p.state}
            {p.message ? ` (${p.message})` : ""}
          </li>
        ))}
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </aside>
  );
}
