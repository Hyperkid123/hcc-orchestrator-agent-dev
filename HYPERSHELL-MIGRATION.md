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
- `dev-bot` gitlink moves `d975996` → `394edfd` → `6b4f296` (top-level profile
  `env` support, dispatcher profile discovery with required `image`, registered
  TypeScript preflights, KEDA-style schedule evaluation — the `a113ed3`
  state proposed by open konflux PR #27 — plus the merged rehor PR #678
  fixes: the deployment-provided Jira bot identity as the default for the
  shared sprint/kanban preflights, and the browser preset screenshot upload
  helper wired to the service gateway — and the merged rehor PR #679 change:
  the profile's approved non-secret `env` reaches the registered TypeScript
  preflights as one read-only `instanceEnv` unit). `6b4f296` is the merge of
  rehor PR #679 on `master` and strictly contains `394edfd` (rehor #678) and
  `a113ed3` (rehor #674), so konflux PR #27 can land before or after this
  draft.
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

1. Rehor core: rehor PR #678 (bot-assigned Jira intake, sandbox screenshot
   uploads) is merged as `394edfd`, and rehor PR #679 (instance env to
   preflights as one unit) is merged as `6b4f296`, the current pin. Still
   required: deploy a dispatcher image built from `6b4f296`+ and rebuild and
   promote this repository's runner image from the same revision with the
   OpenCode V2 closure, then pin the exact digest instead of the `latest`
   placeholder. A green Konflux build is not by itself proof of a deployed
   or promoted image — verify the promoted quay tag/digest and the running
   staging revision before relying on either fix.
2. Model and services auth: verify the dispatcher's model gateway route
   allows `gpt-6.1-sol`/`gpt-6.1-terra` for this agent, and complete the
   authenticated services gateway setup for Jira/GitHub/GitLab (including the
   REHOR-254 risk decision) before enabling live preflights. The `jira-kanban`
   bot-assigned candidate pass is dispatcher-side: the deployment provides
   `BOT_JIRA_EMAIL`, rehor #678/#679 pass it through the run context (the
   `jiraEmail` wiring and the whole approved instance `env` as the
   `instanceEnv` unit) as the default identity, and this profile deliberately
   declares no `with.email`
   override (an explicit non-blank one would still win). Without the
   deployment identity, candidate selection stays unassigned-only.
3. Sandbox runtime: validate the `browser` and `patternfly-mcp` env presets
   inside a HyperShell sandbox, plus `node`/`go`, MCP exposure, native
   subagents, and skills. Screenshots need both sides compatible at runtime:
   the fixed upload helper ships in the browser preset inside this
   repository's runner image (rebuilt from `6b4f296`+), while the service
   gateway route and the upload-only sandbox permission ship in the
   dispatcher image; the legacy unauthenticated upload flow is unchanged.
   Staging checks of the actual upload and the returned asset link are still
   required.
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
