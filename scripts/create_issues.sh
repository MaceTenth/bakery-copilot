#!/usr/bin/env bash
# Create the tickets from docs/tickets.md as GitHub Issues with milestones and labels.
# Run once, from the repo root, after `gh repo create` and `gh auth login`.
set -euo pipefail

for label in feature bug chore; do gh label create "$label" --force >/dev/null 2>&1 || true; done
for ms in "v1 chat" "v2 tools" "v3 limits and deploy"; do gh api -X POST repos/:owner/:repo/milestones -f title="$ms" >/dev/null 2>&1 || true; done

create() { # milestone, label, title, body
  gh issue create --milestone "$1" --label "$2" --title "$3" --body "Done when: $4" >/dev/null && echo "created: $3"
}

create "v1 chat" chore   "Project skeleton: FastAPI app, config from env, health endpoint" "GET /health returns 200 locally; settings load from .env."
create "v1 chat" feature "Database models and startup seed" "tables created at start; sales has 29,115 rows; suppliers has 10."
create "v1 chat" feature "Login with team password and typed name" "right password sets a cookie; wrong password 401; name 2-40 chars."
create "v1 chat" feature "Conversations list and messages API" "a user sees only their conversations; messages return in order."
create "v1 chat" feature "Chat turn with streaming (SSE)" "first token under 2 s on a 3-turn chat; full reply saved once; dropped connection leaves no half-row."
create "v1 chat" feature "Static chat UI: sidebar, bubbles, composer" "works on a phone width; Enter sends, Shift+Enter newline."
create "v1 chat" feature "Markdown rendering of replies" "lists and tables render; plain text falls back when the CDN is blocked."
create "v1 chat" feature "System prompt with today's date and data range" "the prompt names the dataset's first and last dates."
create "v2 tools" feature "sales_query tool: metric, grouping, filters" "totals match the dataset; unknown metric returns an error, not an exception."
create "v2 tools" feature "lookup_supplier tool" "partial, case-insensitive match; unknown name returns known_supplier false."
create "v2 tools" feature "log_invoice tool with dedup, needs-a-look and flag rules" "same source_ref twice is one row; null amount -> needs_a_look; over 5000 -> flagged."
create "v2 tools" feature "Tool loop in the agent (max 6 rounds), tool events to the UI" "the UI shows a chip per tool call; the run row counts tool calls."
create "v2 tools" feature "Image upload: base64 in the turn, reference string, not stored" "a PNG under 5 MB reaches the model; the saved message has has_image."
create "v2 tools" feature "Invoices panel in the UI" "last 50 invoices with status and flag badges."
create "v2 tools" chore   "Eval cases and runner" "python -m evals.run grades 10 cases and appends to history.csv."
create "v3 limits and deploy" feature "Per-user hourly rate limit" "the 31st message in an hour returns 429 with a clear message."
create "v3 limits and deploy" feature "Daily spend cap from the runs table" "at the cap the chat returns 402 back tomorrow."
create "v3 limits and deploy" feature "Cost per run from a price table" "cost_usd on every run; unknown model costs 0."
create "v3 limits and deploy" chore   "Dockerfile, railway.json, health check" "the service builds on Railway and passes /health."
create "v3 limits and deploy" feature "Morning digest: CLI + protected endpoint" "six lines; wrong X-Cron-Secret is 401; webhook POST when configured."
create "v3 limits and deploy" chore   "CI: tests on every PR, evals when the key is present" "a failing test blocks the merge; evals skip cleanly without a key."
create "v3 limits and deploy" chore   "Runbook and first-week watch table" "runbook.md has six entries; docs/watch.md has the six Friday numbers."
