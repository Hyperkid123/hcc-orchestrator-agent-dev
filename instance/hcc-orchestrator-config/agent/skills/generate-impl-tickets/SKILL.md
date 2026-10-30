---
name: generate-impl-tickets
description: >
  Turn approved scan follow-ups into implementation tickets - core-HCC, tenant, or
  both - with acceptance criteria and `repo:` labels, linked back to the scan epic.
  This is the bridge from read-only analysis into Rehor's normal implement->PR
  loop: the tickets it creates are picked up by the backend/frontend personas in a
  later cycle (in this instance or another bot).
when_to_use: >
  ONLY after a `hcc-scan` epic has been aggregated (`last_step: aggregated`) AND a
  human has approved the follow-ups (e.g. an `impl-approved` label or an explicit
  Jira comment). Never auto-generate implementation work from raw findings.
user-invocable: true
allowed-tools:
  - Read
  - "Bash(python3 .claude/skills/service-registry/registry.py *)"
  - mcp__mcp-atlassian__jira_get_issue
  - mcp__mcp-atlassian__jira_search
  - mcp__mcp-atlassian__jira_create_issue
  - mcp__mcp-atlassian__jira_create_issue_link
  - mcp__mcp-atlassian__jira_add_comment
  - mcp__bot-memory__*
---

# generate-impl-tickets — findings -> implementation tickets

## Gate

Do not proceed unless BOTH are true:
- the epic is aggregated (`metadata.followups` present and
  `metadata.scan.last_step: aggregated`), and
- a human has approved (label `impl-approved` on the epic, or an explicit approving
  comment). If not approved, comment asking for sign-off, leave the bot-memory task
  `in_progress`, and set top-level `metadata.last_step: "investigation_posted"` so
  approval comment can wake it.

Idempotency: check for existing implementation children (label `hcc-impl` +
`scan:<epic-key>`) before creating; never duplicate.

## Steps

0. **Resume or create the epic task.** `task_get` by Jira key; update an existing task
   to `in_progress`, or `task_add` one if absent. Do not create a duplicate.
1. Read the epic's approved `metadata.followups` (target, scope, change).
2. For each follow-up, create an implementation ticket with `jira_create_issue`:
   - **Summary:** imperative, scoped to one repo (e.g.
     `<the change the finding calls for> — advisor-backend`).
   - **Description:** the specific change, the evidence link (the analysis ticket +
     file:line), and **acceptance criteria** the implementing persona can verify.
   - **Labels:**
     - `hcc-ai-orchestrator` — the bot pickup label (BOT_LABEL); required or the bot
       never picks the ticket up.
     - `repo:<name>` — the target repo (from the registry / follow-up).
     - `hcc-impl` and `scan:<epic-key>` — provenance.
     - **Do NOT add `needs-investigation`** — these must route to the implement loop
       (backend/frontend persona), not back to the read-only analyst.
   - **Scope tag** in the summary/description: `[core-hcc]` (e.g. insights-rbac,
     inventory-api change) vs `[tenant]` (a consumer service change). "both" =
     create one ticket per repo and link them.
3. **Link** each implementation ticket to its analysis ticket (`relates to`) and to
   the epic.
4. **Comment** on the epic with the created ticket list (table: ticket, repo,
   scope, one-line change).
5. `memory_store` the mapping (finding -> impl ticket) so future scans dedup
   against existing work.
6. Keep the bot-memory task `in_progress` and set top-level
   `metadata.last_step: "investigation_posted"`; set
   `metadata.scan.last_step: "implementation_tickets_generated"`. Human comments can
   then resume the epic-level workflow. A Jira pickup status, no assignee, and the
   corresponding trigger label also make it eligible as new work.

## Handoff to implementation

The created tickets are ordinary jira-kanban work items:
- Carry `hcc-ai-orchestrator` (pickup) but NO `needs-investigation` label -> the
  workflow's normal implement path picks them up.
- The persona is auto-selected by the target repo's tech stack (Go/Python ->
  backend, React/PatternFly -> frontend), per the instance AGENTS.md routing.
- They can be worked by this instance or handed to another bot; the `repo:` label +
  acceptance criteria are all a downstream implement loop needs.

## Notes

- Keep tickets small and single-repo — one reviewable PR each.
- Prefer creating tenant-service tickets and core-HCC tickets as *separate* linked
  items even when a change spans both, so each flows to the right repo/persona.
