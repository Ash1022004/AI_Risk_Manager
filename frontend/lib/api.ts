const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Action = "approve" | "hold" | "escalate";

export type Merchant = {
  id: string;
  name: string;
  category?: string | null;
  features: Record<string, number>;
  status?: string;
  source?: string | null;
};

export type FeatureDriver = {
  feature: string;
  label: string;
  value: number;
  contribution: number;
};

export type Review = {
  id: string;
  merchant_id?: string | null;
  merchant?: Merchant | null;
  status: string;
  risk_score?: number | null;
  risk_band?: string | null;
  recommended_action?: string | null;
  explanation?: string | null;
  feature_drivers: FeatureDriver[];
  policy_hits: Array<Record<string, string>>;
  agent_trace: Array<Record<string, unknown>>;
  human_action?: string | null;
  human_note?: string | null;
  events: Array<Record<string, unknown>>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type Stats = {
  queue_depth: number;
  reviews: number;
  actions: Record<string, number>;
  statuses: Record<string, number>;
  store: string;
};

export type Health = {
  ok: boolean;
  missing_env: string[];
  redis: boolean;
  supabase: boolean;
  store: string;
  model: boolean;
  groq?: { status: string; detail?: string | null };
  groq_ok?: boolean;
  schema_hint?: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string> | undefined) };
  if (init?.body) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    try {
      const data = JSON.parse(text) as { detail?: unknown };
      const detail = data.detail;
      if (typeof detail === "string") throw new Error(detail);
      if (Array.isArray(detail)) throw new Error(detail.map((item) => item.msg || item).join("; "));
    } catch (err) {
      if (err instanceof Error && err.message !== text) throw err;
    }
    throw new Error(text.slice(0, 180) || `Request failed: ${response.status}`);
  }
  return response.json();
}

export const api = {
  health: () => request<Health>("/health"),
  stats: () => request<Stats>("/stats"),
  seeds: () => request<Array<{ slug: string; name: string; category: string }>>("/seeds"),
  reviews: () => request<Review[]>("/reviews"),
  review: (id: string) => request<Review>(`/reviews/${id}`),
  submitSeed: (seed: string) =>
    request<Review>("/reviews", { method: "POST", body: JSON.stringify({ seed }) }),
  override: (id: string, action: Action, note?: string) =>
    request<Review>(`/reviews/${id}/override`, {
      method: "POST",
      body: JSON.stringify({ action, note }),
    }),
};
