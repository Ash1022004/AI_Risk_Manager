"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Action, type Review } from "@/lib/api";

function actionClass(action?: string | null) {
  if (action === "approve") return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
  if (action === "escalate") return "bg-rose-500/15 text-rose-300 border-rose-500/30";
  if (action === "hold") return "bg-amber-500/15 text-amber-300 border-amber-500/30";
  return "bg-white/5 text-zinc-400 border-white/10";
}

export default function ReviewPage() {
  const params = useParams<{ id: string }>();
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Action | null>(null);

  async function refresh() {
    try {
      const next = await api.review(params.id);
      setReview(next);
      setError(null);
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review");
      return null;
    }
  }

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    refresh().then((next) => {
      const inflight = next && ["queued", "scoring", "agent_reviewing"].includes(next.status);
      if (!inflight) return;
      timer = setInterval(async () => {
        if (document.hidden) return;
        const latest = await refresh();
        if (latest && !["queued", "scoring", "agent_reviewing"].includes(latest.status) && timer) {
          clearInterval(timer);
        }
      }, 1500);
    });
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [params.id]);

  async function override(action: Action) {
    setPending(action);
    try {
      setReview(await api.override(params.id, action, "Analyst override from dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Override failed");
    } finally {
      setPending(null);
    }
  }

  if (error && !review) {
    return (
      <div className="px-6 py-10">
        <Link href="/" className="text-sm text-zinc-400 hover:text-zinc-200">
          ← Queue
        </Link>
        <p className="mt-6 text-rose-300">{error}</p>
      </div>
    );
  }

  if (!review) {
    return <div className="px-6 py-10 text-zinc-500">Loading case…</div>;
  }

  const score = review.risk_score ?? 0;
  const maxAbs = Math.max(
    ...review.feature_drivers.map((driver) => Math.abs(driver.contribution)),
    0.0001,
  );

  return (
    <div className="min-h-full px-6 py-6 md:px-10">
      <Link href="/" className="text-sm text-zinc-400 hover:text-zinc-200">
        ← Live queue
      </Link>

      <header className="mt-4 mb-8 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-zinc-500">
            Case {review.id.slice(0, 8)} · {review.status}
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            {review.merchant?.name ?? "Merchant"}
          </h1>
          <p className="mt-1 text-sm text-zinc-400">{review.merchant?.category}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full border px-3 py-1 text-sm ${actionClass(review.recommended_action)}`}>
            agent {review.recommended_action ?? "pending"}
          </span>
          {review.human_action ? (
            <span className={`rounded-full border px-3 py-1 text-sm ${actionClass(review.human_action)}`}>
              human {review.human_action}
            </span>
          ) : null}
          <button
            onClick={() => override("approve")}
            disabled={pending !== null}
            className="rounded-full border border-emerald-500/30 px-3 py-1 text-sm text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-50"
          >
            Override approve
          </button>
          <button
            onClick={() => override("hold")}
            disabled={pending !== null}
            className="rounded-full border border-amber-500/30 px-3 py-1 text-sm text-amber-200 hover:bg-amber-500/10 disabled:opacity-50"
          >
            Override hold
          </button>
          <button
            onClick={() => override("escalate")}
            disabled={pending !== null}
            className="rounded-full border border-rose-500/30 px-3 py-1 text-sm text-rose-200 hover:bg-rose-500/10 disabled:opacity-50"
          >
            Override escalate
          </button>
        </div>
      </header>

      <div className="grid gap-4 xl:grid-cols-[280px_1fr]">
        <aside className="rounded-2xl border border-[#243041] bg-[#121821] p-5">
          <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">LightGBM score</div>
          <div className="mt-4 text-5xl font-semibold tracking-tight">
            {review.risk_score == null ? "—" : score.toFixed(2)}
          </div>
          <div className="mt-2 text-sm text-zinc-400">{review.risk_band ?? "awaiting score"} band</div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-amber-400"
              style={{ width: `${Math.min(score * 100, 100)}%` }}
            />
          </div>
        </aside>

        <section className="rounded-2xl border border-[#243041] bg-[#121821] p-5">
          <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">Agent explanation</div>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-zinc-200">
            {review.explanation || "The agent is still reviewing this merchant."}
          </p>
          {review.human_action ? (
            <p className="mt-4 text-xs text-amber-200">
              Human override: {review.human_action}
              {review.human_note ? ` — ${review.human_note}` : ""}
            </p>
          ) : null}
        </section>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-[#243041] bg-[#121821] p-5">
          <div className="mb-4 text-xs uppercase tracking-[0.16em] text-zinc-500">
            Feature drivers
          </div>
          <div className="space-y-3">
            {review.feature_drivers.length === 0 && (
              <p className="text-sm text-zinc-500">Waiting for model contributions.</p>
            )}
            {review.feature_drivers.map((driver) => (
              <div key={driver.feature}>
                <div className="mb-1 flex justify-between text-xs">
                  <span className="text-zinc-300">{driver.label}</span>
                  <span className="font-mono text-zinc-500">
                    {driver.value} · {driver.contribution > 0 ? "+" : ""}
                    {driver.contribution}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
                  <div
                    className={driver.contribution >= 0 ? "h-full bg-rose-400" : "h-full bg-emerald-400"}
                    style={{ width: `${(Math.abs(driver.contribution) / maxAbs) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-[#243041] bg-[#121821] p-5">
          <div className="mb-4 text-xs uppercase tracking-[0.16em] text-zinc-500">Policy hits</div>
          <div className="space-y-2">
            {review.policy_hits.length === 0 && (
              <p className="text-sm text-zinc-500">No policy evaluation yet.</p>
            )}
            {review.policy_hits.map((hit, index) => (
              <div key={`${hit.code}-${index}`} className="rounded-xl border border-white/5 bg-white/2 px-3 py-2">
                <div className="text-sm text-zinc-200">{hit.message}</div>
                <div className="mt-1 font-mono text-[11px] text-zinc-500">
                  {hit.code} · floor {hit.action_floor}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="mt-4 rounded-2xl border border-[#243041] bg-[#121821] p-5">
        <div className="mb-4 text-xs uppercase tracking-[0.16em] text-zinc-500">
          Agent + pipeline timeline
        </div>
        <ol className="space-y-3">
          {review.events.map((event, index) => (
            <li key={String(event.id ?? index)} className="flex gap-3 text-sm">
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-300" />
              <div>
                <div className="font-medium text-zinc-200">{String(event.event_type)}</div>
                <div className="font-mono text-[11px] text-zinc-500">
                  {event.created_at ? new Date(String(event.created_at)).toLocaleString() : ""}
                </div>
              </div>
            </li>
          ))}
          {review.agent_trace.map((step, index) => (
            <li key={`trace-${index}`} className="flex gap-3 text-sm">
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-sky-300" />
              <div>
                <div className="font-medium text-zinc-200">
                  {String(step.type)}
                  {step.name ? ` · ${String(step.name)}` : ""}
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  {step.type === "error"
                    ? String(step.message || "Agent fallback used")
                    : step.type === "fallback"
                      ? "Used LightGBM + policy because Groq did not return a decision."
                      : step.name
                        ? `Called ${String(step.name)}`
                        : JSON.stringify(step)}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
