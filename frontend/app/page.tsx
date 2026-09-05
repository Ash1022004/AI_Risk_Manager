"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Health, type Review, type Stats } from "@/lib/api";

function actionClass(action?: string | null) {
  if (action === "approve") return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
  if (action === "escalate") return "bg-rose-500/15 text-rose-300 border-rose-500/30";
  if (action === "hold") return "bg-amber-500/15 text-amber-300 border-amber-500/30";
  return "bg-white/5 text-zinc-400 border-white/10";
}

function statusClass(status: string) {
  if (status === "decided" || status === "overridden") return "text-emerald-300";
  if (status === "failed") return "text-rose-300";
  return "text-amber-300";
}

function formatTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const IN_FLIGHT = new Set(["queued", "scoring", "agent_reviewing"]);

function isInFlight(review: Review) {
  return IN_FLIGHT.has(review.status);
}

export default function QueuePage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [live, setLive] = useState(false);

  async function refresh(includeHealth = false) {
    try {
      const [nextReviews, nextStats, nextHealth] = await Promise.all([
        api.reviews(),
        api.stats(),
        includeHealth ? api.health() : Promise.resolve(null),
      ]);
      setReviews(nextReviews);
      setStats(nextStats);
      if (nextHealth) setHealth(nextHealth);
      setError(null);
      return nextReviews;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend unreachable");
      return [];
    }
  }

  useEffect(() => {
    refresh(true).then((rows) => {
      if (rows.some(isInFlight)) setLive(true);
    });
  }, []);

  useEffect(() => {
    if (!live) return;
    const timer = setInterval(async () => {
      if (document.hidden) return;
      const rows = await refresh(false);
      if (!rows.some(isInFlight)) setLive(false);
    }, 1500);
    return () => clearInterval(timer);
  }, [live]);

  async function submit(seed: string) {
    setPending(seed);
    setLive(true);
    try {
      await api.submitSeed(seed);
      await refresh(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="min-h-full px-6 py-6 md:px-10">
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="mb-1 font-mono text-xs uppercase tracking-[0.2em] text-amber-300/80">
            Bumblebee-style reviewer
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">AI Risk Manager</h1>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            LightGBM scores merchant signals. A Groq agent explains the decision and recommends
            approve, hold, or escalate.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => submit("high-risk")}
            disabled={pending !== null}
            className="rounded-full border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-sm text-rose-100 hover:bg-rose-500/20 disabled:opacity-50"
          >
            {pending === "high-risk" ? "Queuing…" : "Submit high-risk"}
          </button>
          <button
            onClick={() => submit("borderline")}
            disabled={pending !== null}
            className="rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 hover:bg-amber-500/20 disabled:opacity-50"
          >
            {pending === "borderline" ? "Queuing…" : "Submit borderline"}
          </button>
          <button
            onClick={() => submit("clean")}
            disabled={pending !== null}
            className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-500/20 disabled:opacity-50"
          >
            {pending === "clean" ? "Queuing…" : "Submit clean"}
          </button>
        </div>
      </header>

      <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Queue depth" value={stats?.queue_depth ?? "—"} />
        <Stat label="Reviews" value={stats?.reviews ?? "—"} />
        <Stat
          label="Actions"
          value={`${stats?.actions.approve ?? 0} / ${stats?.actions.hold ?? 0} / ${stats?.actions.escalate ?? 0}`}
          hint="approve / hold / escalate"
        />
        <Stat
          label="Store / Groq"
          value={`${health?.store ?? "—"} · ${health?.groq?.status ?? "unknown"}`}
          hint={
            health?.groq?.status === "error"
              ? "Groq key is invalid. Cases still score with LightGBM + policy."
              : health?.supabase
                ? "Supabase connected"
                : health?.schema_hint || "Redis-backed store until schema.sql is applied"
          }
        />
      </section>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {error}
        </div>
      )}

      <section className="overflow-hidden rounded-2xl border border-[#243041] bg-[#121821]">
        <div className="border-b border-[#243041] px-5 py-3 text-xs uppercase tracking-[0.16em] text-zinc-500">
          Live review queue
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-190 text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-5 py-3 font-medium">Merchant</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Score</th>
                <th className="px-5 py-3 font-medium">Action</th>
                <th className="px-5 py-3 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {reviews.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-zinc-500">
                    No reviews yet. Submit a seed merchant to start the live demo.
                  </td>
                </tr>
              )}
              {reviews.map((review) => (
                <tr key={review.id} className="border-t border-[#243041] hover:bg-white/2">
                  <td className="px-5 py-4">
                    <Link href={`/reviews/${review.id}`} className="block">
                      <div className="font-medium text-zinc-100">
                        {review.merchant?.name ?? "Unknown merchant"}
                      </div>
                      <div className="text-xs text-zinc-500">
                        {review.merchant?.category ?? "—"} · {review.id.slice(0, 8)}
                      </div>
                    </Link>
                  </td>
                  <td className={`px-5 py-4 font-mono text-xs ${statusClass(review.status)}`}>
                    {review.status}
                  </td>
                  <td className="px-5 py-4 font-mono text-xs">
                    {review.risk_score == null ? "—" : review.risk_score.toFixed(3)}
                    {review.risk_band ? (
                      <span className="ml-2 text-zinc-500">{review.risk_band}</span>
                    ) : null}
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex rounded-full border px-2.5 py-1 text-xs ${actionClass(review.recommended_action)}`}
                    >
                      {review.recommended_action ?? "pending"}
                    </span>
                  </td>
                  <td className="px-5 py-4 font-mono text-xs text-zinc-500">
                    {formatTime(review.updated_at || review.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="rounded-2xl border border-[#243041] bg-[#121821] px-4 py-4">
      <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
      {hint ? <div className="mt-1 text-xs text-zinc-500">{hint}</div> : null}
    </div>
  );
}
