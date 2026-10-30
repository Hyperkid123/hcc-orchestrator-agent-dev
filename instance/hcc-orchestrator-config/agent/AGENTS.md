# hcc-orchestrator-agent-dev — Additional Instructions

OpenCode-native profile instructions (the legacy `CLAUDE.md` was removed with the
Claude runtime; git history preserves it for rollback).

## Tool-call narration

Keep the runner's Ultra Caveman output policy. Apply these additional rules across
all subagents and skills:

- Call tools directly. After a result, make the next tool call without commentary.
  Do not emit text solely to announce, acknowledge, or describe routine work.
- No tool-call preambles, transition comments ("looks good — now on to this"),
  self-congratulation, repeated plans, or paraphrases of tool results.
- Emit task prose only for necessary clarification, actionable blockers, security
  warnings, irreversible-action confirmation, or a concise final outcome.
- Continue required status tool calls, progress checkpoints, and structured
  metadata. Do not duplicate those updates in narration.
- Keep human-facing deliverables in normal prose with all required formats and
  evidence: Jira comments, PR/MR descriptions and review replies, commits,
  documentation, and code comments.

## Target Repos
- **APIcast**: `https://github.com/3scale/APIcast`
- **turnpike**: `https://github.com/RedHatInsights/turnpike`
- **chrome-service-backend**: `https://github.com/RedHatInsights/chrome-service-backend`
- **quickstarts**: `https://github.com/RedHatInsights/quickstarts`
- **notifications-backend**: `https://github.com/RedHatInsights/notifications-backend`
- **inventory-api**: `https://github.com/project-kessel/inventory-api`
- **insights-rbac**: `https://github.com/project-kessel/insights-rbac`
- **export-service-go**: `https://github.com/RedHatInsights/export-service-go`
- **pdf-generator**: `https://github.com/RedHatInsights/pdf-generator`
- **sources-api-go**: `https://github.com/RedHatInsights/sources-api-go`
- **insights-ingress-go**: `https://github.com/RedHatInsights/insights-ingress-go`
- **payload-tracker-go**: `https://github.com/RedHatInsights/payload-tracker-go`
- **insights-storage-broker**: `https://github.com/RedHatInsights/insights-storage-broker`
- **entitlements-api-go**: `https://github.com/RedHatInsights/entitlements-api-go`
- **astro-virtual-assistant**: `https://github.com/RedHatInsights/astro-virtual-assistant`
- **hermod**: `https://github.com/RedHatInsights/hermod`
- **scheduler**: `https://github.com/RedHatInsights/scheduler`
- **insights-chrome**: `https://github.com/RedHatInsights/insights-chrome`
- **advisor-backend**: `https://github.com/RedHatInsights/advisor-backend`
- **ccx-data-pipeline**: `https://gitlab.cee.redhat.com/ccx/ccx-data-pipeline`
- **cloud-connector**: `https://github.com/RedHatInsights/cloud-connector`
- **cloudigrade**: `https://github.com/cloudigrade/cloudigrade`
- **compliance-backend**: `https://github.com/RedHatInsights/compliance-backend`
- **config-manager**: `https://github.com/RedHatInsights/config-manager`
- **content-sources-backend**: `https://github.com/content-services/content-sources-backend`
- **koku**: `https://github.com/project-koku/koku`
- **insights-host-inventory**: `https://github.com/RedHatInsights/insights-host-inventory`
- **malware-detection-backend**: `https://gitlab.cee.redhat.com/insights-platform/malware-detection-backend`
- **patchman-engine**: `https://github.com/RedHatInsights/patchman-engine`
- **playbook-dispatcher**: `https://github.com/RedHatInsights/playbook-dispatcher`
- **insights-remediations**: `https://github.com/RedHatInsights/insights-remediations`
- **rhsm-api-proxy**: `https://github.com/RedHatInsights/rhsm-api-proxy`
- **rhsm-api**: `https://gitlab.cee.redhat.com/it-pnt/rhsm/rhsm-api`
- **digital-roadmap-backend**: `https://github.com/RedHatInsights/digital-roadmap-backend`
- **ros-backend**: `https://github.com/RedHatInsights/ros-backend`
- **automation-analytics-backend**: `https://gitlab.cee.redhat.com/automation-analytics/automation-analytics-backend`
- **vulnerability-engine**: `https://github.com/RedHatInsights/vulnerability-engine`

## Detected Tech Stacks
- **hcc-orchestrator**: envs=[], personas=[analyst, backend, frontend]

## Subagent routing

`hcc-ai-orchestrator` is the bot pickup label (`BOT_LABEL`) — every ticket the bot
works carries it. The labels below select what to *do* with a picked-up ticket, and
subagent choice overrides the default tech-stack auto-detection:

1. **`hcc-scan` label (a scan-coordinator epic) → run a scan *skill*, not a subagent.**
   - epic also has **`scan-aggregate`** → `/aggregate-scan`: post/refresh the
     epic-level summary from the children, then **remove the `scan-aggregate` label**
     so it does not re-aggregate on every subsequent pickup.
   - else → `/plan-scan` (additive — creates only the analysis children that do not
     exist yet, so re-picking-up an epic to widen its scope is safe).
2. **`needs-investigation` + `scan:<epic>` label → `analyst` subagent (READ-ONLY).**
   Never modify a target repo, never push, never open a PR. Work via `/scan-service`.
   See below.
3. **`persona:<name>` label → that subagent**, if present (explicit override).
4. **Otherwise → auto-detect by the target repo's tech stack** (Go/Python/Ruby/Java
   → `backend`; React/PatternFly → `frontend`).

Implementation tickets from a scan carry `hcc-ai-orchestrator` + `hcc-impl` +
`repo:<name>` and **no** `needs-investigation` label, so they route to
`backend`/`frontend` and flow through the normal implement→PR loop.

Tickets involving Clowder Dependency Endpoints or clowder migrations -> `clowder-v2-assessment` first. Only hand off to `clowder-v2-migration-kessel` when assessment produces a migration packet with no decision-required fields. No Kessel SDK or env/config-only discovery -> gate note, no implementation; recommend a follow-up ticket to add the SDK. Auth: Kessel SDK `OAuth2ClientCredentials` bearer for cross-cluster gateway auth; replace PSK with it when `authenticated: true`; keep `x-rh-identity` as end-user context. For ref provisioning or cutover, also read `personas/clowder-v2/provisioning.md`.

## Cross-service scan workflow (analysis → tickets → implementation)

A scan runs in four human-gated stages. The parallelism is in the *loop* (one
service per cycle across many cycles), not in a single cycle. Every ticket below also
carries `hcc-ai-orchestrator` (the bot pickup label).

1. **Plan** — a scan-coordinator epic (labels `hcc-ai-orchestrator` + `hcc-scan`,
   focus in its summary) is picked up → run `/plan-scan`. It resolves the target set
   from `/service-registry` and creates one read-only analysis child per service
   (`needs-investigation` + `repo:<name>` + `scan:<epic-key>`), linked to the epic.
2. **Analyze** — each analysis child is worked one-per-cycle by the `analyst`
   subagent via `/scan-service`: read-only audit → per-service Jira comment (verdict +
   file:line evidence + checklist) → `memory_store` → `metadata.findings` on the task.
3. **Aggregate** — this stage is **human-triggered**: when the analyses look done, a
   human adds the **`scan-aggregate`** label to the epic and moves it back into the
   pickup queue (a `BOT_KANBAN_STATUSES` status — e.g. *To Do* — with assignee empty;
   an *In Progress* epic is not re-picked-up). On that pickup, `/aggregate-scan` rolls
   the children into an epic-level markdown table (per-service findings + common
   patterns + outliers + follow-ups) posted on the epic, reconciles against the
   registry so no target is skipped, and removes the `scan-aggregate` label. Re-add the
   label anytime to refresh the summary (e.g. after an expansion adds services).
4. **Generate implementation tickets** — ONLY after a human approves the follow-ups
   (`impl-approved` on the epic), `/generate-impl-tickets` turns them into
   `hcc-impl` tickets (core-hcc / tenant / both), linked back, which then flow through
   the normal implement loop.

### Task lifecycle and Kanban preflight

The shared Jira Kanban preflight treats every `in_progress` task without a PR as
interrupted unless top-level `metadata.last_step` is exactly `investigation_posted`.
For scan epics and analysis tasks that must resume on human comments, keep the
bot-memory task `in_progress` and set top-level `metadata.last_step` to exactly
`investigation_posted` when stage work completes. Store workflow phase in nested
metadata (for epics, `metadata.scan.last_step`). This suppresses false interrupted
starts while preserving comment polling. A human can also requeue an epic by adding
the stage label, moving its Jira issue to a configured pickup status (normally
*New*), and clearing assignee. At max task capacity, preflight searches only
`needs-investigation` candidates, so add a plain-text Jira comment with the trigger or
wait for capacity; comment triage runs before that capacity check. Reactivate existing
task record as needed; do not create a duplicate.

`task_update(status="paused", paused_reason=...)` means bot-memory task is excluded
from active-task triage and comment polling. Reserve it for waits that should require
an explicit status/unpause action; do not use it for scan work where humans may resume
through comments. Keep workflow-specific terminal values such as `analysis_posted`,
`assessment_posted`, `aggregated`, `all_analyses_complete`, `migration_packet_posted`,
or `feedback_addressed` out of top-level `metadata.last_step` when completed no-PR work
must remain comment-watchable.

Read-only enforcement for analysis: the `scan-service` skill's `allowed-tools`
exclude `Edit`/`Write`/push/PR, and the `analyst` subagent forbids mutation. A
hard runtime guarantee (a PreToolUse deny-hook) is a framework-level ask — the
config-only instance cannot currently ship one (see `docs/scan-workflow.md`).

## Team Conventions

<!-- Fill in team-specific conventions after scaffolding -->
<!-- Examples: version managers, test commands, PR review norms -->

## OpenCode

This profile uses native subagents in `.opencode/agents/` instead of a persona
directory per role. The shared workflow guidance may still refer to
`personas/<name>/prompt.md`; map those role names to the matching native subagents
and do not search for the deleted persona files. Exception:
`personas/clowder-v2/` reference files still exist in this profile and are
referenced by the clowder agents.

OpenCode V2 does not expose the legacy LSP tool. Use each repository's
typecheck, lint, and test commands instead.
