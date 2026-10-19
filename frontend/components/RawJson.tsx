"use client";
import { useState } from "react";

export default function RawJson({ data }: { data: unknown }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(data, null, 2);
  return (
    <div className="raw">
      <button type="button" onClick={() => setOpen(!open)}>
        {open ? "Hide raw JSON" : "Show raw JSON"}
      </button>
      {open ? (
        <>
          <button
            type="button"
            onClick={() => {
              navigator.clipboard?.writeText(text);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            type="button"
            onClick={() => {
              const blob = new Blob([text], { type: "application/json" });
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = "company-research.json";
              a.click();
              URL.revokeObjectURL(a.href);
            }}
          >
            Download JSON
          </button>
          <pre>{text}</pre>
        </>
      ) : null}
    </div>
  );
}
