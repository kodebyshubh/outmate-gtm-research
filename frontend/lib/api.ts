import { Report } from "./types";

// The browser only talks to our own backend. No third-party keys exist in frontend code.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function runResearch(
  body: { company_name?: string; website?: string; objective?: string; refresh?: boolean },
  signal?: AbortSignal
): Promise<Report> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e: any) {
    if (e?.name === "AbortError") throw new Error("Cancelled.");
    throw new Error("Could not reach the backend. Is it running on " + API_BASE + "?");
  }
  if (res.status === 422) {
    const data = await res.json().catch(() => null);
    const msg = data?.detail?.[0]?.msg || "Please provide a company name or a website.";
    throw new Error(msg.replace("Value error, ", ""));
  }
  if (res.status === 504) throw new Error("Research took too long. Please try again.");
  if (!res.ok) throw new Error(`The backend returned an error (HTTP ${res.status}).`);
  return res.json();
}
