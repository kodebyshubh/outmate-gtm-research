import { Status } from "@/lib/types";

const LABELS: Record<Status, { text: string; icon: string }> = {
  verified: { text: "Verified", icon: "✓" },
  "provider-reported": { text: "Provider-reported", icon: "◆" },
  inferred: { text: "Inferred", icon: "∼" },
  unavailable: { text: "Unavailable", icon: "∅" },
};

// Text plus icon plus color, so status never relies on color alone.
export default function StatusBadge({ status }: { status: Status }) {
  const l = LABELS[status];
  return (
    <span className={`badge badge-${status}`}>
      <span aria-hidden="true">{l.icon}</span> {l.text}
    </span>
  );
}
