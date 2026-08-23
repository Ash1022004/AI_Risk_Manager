create extension if not exists pgcrypto;

create table if not exists merchants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  category text,
  features jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  source text default 'demo',
  created_at timestamptz not null default now()
);

create table if not exists reviews (
  id uuid primary key default gen_random_uuid(),
  merchant_id uuid references merchants(id) on delete cascade,
  status text not null default 'queued',
  risk_score double precision,
  risk_band text,
  recommended_action text,
  explanation text,
  feature_drivers jsonb not null default '[]'::jsonb,
  policy_hits jsonb not null default '[]'::jsonb,
  agent_trace jsonb not null default '[]'::jsonb,
  human_action text,
  human_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists review_events (
  id uuid primary key default gen_random_uuid(),
  review_id uuid references reviews(id) on delete cascade,
  event_type text not null,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists reviews_status_idx on reviews (status);
create index if not exists reviews_created_idx on reviews (created_at desc);
create index if not exists review_events_review_idx on review_events (review_id, created_at);

alter table merchants enable row level security;
alter table reviews enable row level security;
alter table review_events enable row level security;
