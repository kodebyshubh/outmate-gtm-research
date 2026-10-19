export type Status = "verified" | "provider-reported" | "inferred" | "unavailable";

export interface Source {
  url?: string | null;
  title?: string | null;
  published_date?: string | null;
  quote?: string | null;
}

export interface FieldData {
  value: any;
  status: Status;
  sources: Source[];
  note?: string | null;
}

export interface ProviderStatus {
  name: string;
  state: string;
  message: string;
}

export interface Report {
  company_name: FieldData;
  website_domain: FieldData;
  company_description: FieldData;
  industry: FieldData;
  target_market: FieldData;
  employee_size: FieldData;
  recent_growth_signals: FieldData[];
  potential_gtm_opportunity: FieldData;
  decision_makers: FieldData[];
  contact_information: FieldData;
  source_urls: string[];
  providers: ProviderStatus[];
  warnings: string[];
  dropped_claims: { field: string; claimed_value: any; reason: string }[];
  mock_enrichment: { label: string; people: any[]; company: any } | null;
  evidence: { id: string; url: string; title?: string; published_date?: string; highlight: string; category: string }[];
  generated_at: string;
}
