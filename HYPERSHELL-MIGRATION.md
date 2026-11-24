# HCC Orchestrator HyperShell migration draft (REHOR-282)

Status: preparation only. This draft prepares the `hcc-orchestrator-config`
dispatcher profile. It does not enroll this repository in the dispatcher,
publish or promote an image, change app-interface/GitOps, deploy anything, or
authorize a cutover. REHOR-187 (OpenCode runtime on the classic Deployment) is
closed historical context; this draft changes no legacy runtime behavior.

The legacy `deploy/template.yaml`, its KEDA `ScaledObject`, NetworkPolicies,
and app-interface registration are untouched.

## Profile changes

- `instance/hcc-orchestrator-config/agent/instance.yaml` declares the
  dispatcher profile fields: `image` (repository + placeholder `latest` tag),
  top-level non-secret `env` identity (`BOT_INSTANCE_ID`, `BOT_LABEL`,
  `BOT_BOARD_NAME`, `BOT_JIRA_PROJECT`, `BOT_CONFIG_PATH`,
  `BOT_EXECUTION_ENGINE`), explicit `preflights`
  (`gh-pr-status`, `gl-mr-status`, `jira-kanban` with the legacy inputs
  `project=RHCLOUD`, `label=hcc-ai-orchestrator`, statuses
  `New/Backlog/To Do`), and a `schedule` mirroring the legacy KEDA window
  (Mon–Fri 09:00–23:00 Europe/Prague). Source of the live values: the
  app-interface SaaS file `hcc-orchestrator-agent-dev-deploy.yml` parameters
  plus the legacy template defaults.
- `dev-bot` gitlink moves `d975996` → `a113ed3` (top-level profile `env`
  support, dispatcher profile discovery with required `image`, registered
  TypeScript preflights, KEDA-style schedule evaluation). This is the same
  digest proposed by open konflux PR #27; there is no competing standalone
  bump.
- Model tiering on the existing native roles (no roles added, no prompts
  duplicated, permissions untouched):
  - `orchestrator-coordinator` stays `rehor-openai/gpt-6.1-sol` (coordination).
  - `backend`, `frontend`, `clowder-v2-migration-kessel` move
    `gpt-6-luna` → `gpt-6.1-terra` (substantial implementers).
  - `clowder-v2-assessment` moves `gpt-6-luna` → `gpt-6.1-terra` (its G1–G4
    gate classification, decision-required blocking rules, and auth semantics
    are substantial decision work).
  - `analyst` stays `gpt-6-luna` (bounded, cursory-by-default read-only scan).
  - `opencode-deployment.json` declares `gpt-6.1-terra` (packaged runtime
    default; absent from this instance's catalog until now). Proxy stage
    allowlist already includes it
    (`OPENAI_ALLOWED_MODELS=gpt-6.1-sol,gpt-6-luna,gpt-6.1-terra`).

## Gates before cutover

1. Rehor core: merge the dispatcher fixes tracked by rehor PR #678
   (bot-assigned Jira intake, sandbox screenshot uploads), deploy a dispatcher
   image containing them and `a113ed3`+; rebuild and promote this repository's
   runner image from the same revision with the OpenCode V2 closure, then pin
   the exact digest instead of the `latest` placeholder.
2. Model and services auth: verify the dispatcher's model gateway route
   allows `gpt-6.1-sol`/`gpt-6.1-terra` for this agent, and complete the
   authenticated services gateway setup for Jira/GitHub/GitLab (including the
   REHOR-254 risk decision) before enabling live preflights. The
   `jira-kanban` bot-assigned candidate pass depends on the deployment
   identity wiring from gate 1.
3. Sandbox runtime: validate the `browser` and `patternfly-mcp` env presets
   inside a HyperShell sandbox (screenshots depend on gate 1), plus
   `node`/`go`, MCP exposure, native subagents, and skills.
4. Live workflow: run a no-work cycle (no sandbox starts) and one
   representative jira-kanban work cycle in an approved test context, covering
   claim, implementation, PR creation, feedback, and cleanup. Never run the
   dispatcher and the legacy deployment against this instance at the same
   time; scale the legacy deployment to zero before dispatcher cutover.
5. Human review of the profile diff, identities, schedule, model routing,
   image reference, and rollback readiness. app-interface/GitOps enrollment is
   a separate change.

## Rollback

Remove this repository from the dispatcher's configured repository list and
let in-flight sessions drain. Keep the previous runner image and the legacy
deployment (including KEDA window and image digest) available; restore
replicas if the legacy path was paused. The legacy deploy template is
untouched by this draft, so no template rollback is required.
