# OpenCode V2 Migration — hcc-orchestrator-agent-dev

Migration and rollback record for the `hcc-orchestrator-agent-dev` dev-bot
instance (REHOR-187). For the full migration contract — runtime architecture,
coordinator boundary, provider allowlist policy, and image acceptance gates —
see `dev-bot/docs/migrations/opencode-migration.md` in the `dev-bot` submodule.

## Prior state

- `dev-bot` gitlink: `30dd8cc` (49 commits behind OpenShift-Fleet/rehor master;
  pre-OpenCode coordinator).
- `BOT_EXECUTION_ENGINE` defaulted to `python` (Claude SDK runner).
- Runtime `claude`, provider `vertex`, default Claude model via
  `VERTEX_ALLOWED_MODELS`.
- Profile at `instance/hcc-orchestrator-config` (`BOT_CONFIG_PATH`):
  `CLAUDE.md` instructions, five persona directories
  (`analyst`, `backend`, `frontend`, `clowder-v2-assessment`,
  `clowder-v2-migration-kessel`) plus `clowder-v2` reference material, and
  `.claude/skills`-compatible `skills/`.

## New state

- `dev-bot` gitlink: `bbc7bfe` (OpenShift-Fleet/rehor master; includes REHOR-200
  OpenCode native V2 and REHOR-211 per-cycle USD cost budget).
- `BOT_EXECUTION_ENGINE: coordinator` — set via GitOps in app-interface
  (`data/services/insights/platform-frontend-ai-dev/hcc-orchestrator-agent-dev-deploy.yml`);
  the template default remains `python` for rollback.
- Runtime `opencode`, provider `rehor-openai`, basic model `gpt-6-luna`
  (worker subagents, high reasoning effort), Sol `gpt-6.1-sol` for the
  coordinator primary agent (medium effort).
- Model access through the shared proxy's OpenAI-compatible gateway:
  `REHOR_MODEL_PROXY_URL: http://devbot-proxy:8450/v1`.
  `OPENAI_ALLOWED_MODELS` on the shared proxy already includes both
  `gpt-6.1-sol` and `gpt-6-luna`.
- Managed egress (SandboxTemplate networkPolicy, see below) allows TCP/8450 to
  `devbot-proxy`.

## Deployment shape migration

The workload moved from a classic `Deployment` + metrics `Service` +
`${BOT_NAME}-egress`/`${BOT_NAME}-ingress` NetworkPolicies to the OpenShell
deployment pattern (RHCLOUD-50068), same as `hcc-framework-agent-dev`:

- `SandboxTemplate` (`extensions.agents.x-k8s.io/v1beta1`, name `${BOT_NAME}`) —
  the pod blueprint with `networkPolicyManagement: Managed`: managed ingress
  from `agent-sandbox-system` / `sandbox-router`, managed egress to
  `devbot-proxy` (3128, 9090, 8443, 8444, 8446, 8450), `memory-server` (8080),
  and `openshift-dns` (5353 UDP/TCP). The bot container keeps every env var
  from the classic Deployment (plus `CYCLE_RUNS_API_URL` for cycle record
  verification) and pins the image by digest: `${REGISTRY_IMG}@${IMAGE_DIGEST}`.
- `SandboxWarmPool` (`extensions.agents.x-k8s.io/v1beta1`, name `${BOT_NAME}`) —
  KEDA scales the warm pool, not a Deployment; `spec.replicas` from
  `BOT_REPLICAS`.
- KEDA `ScaledObject` `${BOT_NAME}-cron-scaler` — targets the
  `SandboxWarmPool`; cron window from `KEDA_TIMEZONE`/`KEDA_CRON_START`/
  `KEDA_CRON_END` (defaults Europe/Prague, 09:00–23:00 weekdays).
- `NetworkPolicy` `${BOT_NAME}-metrics-ingress` — Prometheus scrape from
  `openshift-customer-monitoring` on 9091. The metrics `Service` and both old
  NetworkPolicies are dropped.

The agent-sandbox controller enforces the filesystem boundary: read-only
rootfs with writable `emptyDir` mounts at `/home/botuser/repos`,
`/home/botuser/data`, and `/tmp`. See `dev-bot/docs/openshell-deployment.md`
and the framework template this mirrors
(`/Users/martin/rehor/hcc-framework-agent-dev` → `deploy/template.yaml`).

Rollback of the runtime must also revert the template shape: the previous
config revision contains the classic `Deployment` (plus its `Service` and
NetworkPolicies), so restoring the old image digest + config revision with
`BOT_EXECUTION_ENGINE=python` and `runtime: claude` redeploys the pre-OpenShell
workload shape as well.

## File conversion map

| Prior (Claude) | New (OpenCode) | Notes |
|---|---|---|
| `agent/personas/<role>/prompt.md` (analyst, backend, frontend, clowder-v2-assessment, clowder-v2-migration-kessel) | `agent/.opencode/agents/<role>.md` | Full prompt bodies carried over; persona `mcp.json` files were empty and are dropped. |
| — | `agent/.opencode/agents/orchestrator-coordinator.md` | New primary agent; carries the CLAUDE.md persona-routing logic. |
| `agent/CLAUDE.md` | `agent/AGENTS.md` | All sections carried over (tool-call narration, Target Repos, Detected Tech Stacks, subagent routing, scan workflow, task lifecycle, team conventions) plus an OpenCode section. `CLAUDE.md` removed — superseded by the OpenCode config; git history preserves it. |
| — | `agent/opencode.json` | `default_agent: orchestrator-coordinator`, `experimental.subagent_depth: 1`. |
| — | `opencode-deployment.json` | Sibling of `agent/`; `rehor-openai` provider (OpenAI Responses package) with `gpt-6.1-sol` (`reasoningEffort: medium`) and `gpt-6-luna` (`reasoningEffort: high` — bridges the gap to Sol for basic work). Wired via `REHOR_OPENCODE_DEPLOYMENT_CONFIG`. |
| `agent/skills/` | unchanged | Legacy skills still install to `.claude/skills`; OpenCode keeps `.claude/skills` compatibility. |
| `agent/mcp.json` | unchanged | `mcp-atlassian` via `${JIRA_MCP_URL}`. |
| `agent/personas/clowder-v2/` | unchanged | Reference material (`migration-common.md`, `provisioning.md`, `references/` incl. `clowder-migration.csv`); still referenced by the clowder subagents. |

`instance.yaml` selectors added (`runtime: opencode`, `provider: rehor-openai`,
`model: gpt-6-luna`). Model policy: **Luna is the basic model** (worker
subagents, high reasoning effort to bridge the gap); **Sol is for the more
challenging coordination lane** (orchestrator-coordinator primary agent,
medium effort). `claude_md.strategy` and the `CLAUDE.md`/Vertex runtime env
(`CLAUDE_CODE_SKIP_VERTEX_AUTH`, `ANTHROPIC_*`, `CLOUD_ML_REGION`) were removed
as Claude leftovers superseded by the OpenCode configuration.

## Rollback procedure

1. Redeploy the previous immutable image digest and config revision.
2. Set `BOT_EXECUTION_ENGINE=python` (GitOps parameter).
3. Revert this migration commit in the instance repository: it restores the
   `instance.yaml` Claude defaults (`runtime: claude`, `provider: vertex`,
   `claude_md` strategy), `agent/CLAUDE.md`, the persona directories, the
   Vertex runtime env, the classic `Deployment` template shape, and the
   previous `dev-bot` gitlink (`30dd8cc`) — the full pre-OpenCode profile.

Note: changing the provider alone is **not** a runtime rollback. The Claude
runtime requires `BOT_EXECUTION_ENGINE=python` plus `runtime: claude` /
`provider: vertex`. `GCP_*`/`VERTEX_ALLOWED_MODELS` remain as template
parameters only because the app-interface caller still supplies them
(deprecated contract); the workload no longer consumes them on the OpenCode
path.
