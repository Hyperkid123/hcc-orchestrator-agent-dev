# Known Platform Dependency V2 Keys (bundled reference)

The Scope Gate limits this persona to four platform-owned dependencies: RBAC, Kessel, Export service, and Sources.
Because these are few, named, and centrally owned, their Clowder V2 app/deployment keys are **static platform
facts** — they change only when the owning team restructures their `ClowdApp`, not per consumer. Look them up here
first. Do not re-derive them by crawling another team's repo on a routine ticket; that doesn't scale past a handful
of dependencies and depends on network reachability this bot may not have.

## Table

| Dependency | App key | Deployment key | Public | Private | apiPath | Notes | Evidence | Verified |
|---|---|---|---|---|---|---|---|---|
| RBAC | `rbac` | `service` | Yes | No | `rbac` | Only deployment declaring a `webServices` block; `worker-service`, `scheduler-service`, `rbac-kafka-consumer`, `rbac-postgres-exporter` do not expose one (exporter has `webServices.metrics` only, not an API) | `insights-rbac/deploy/rbac-clowdapp.yml:404-409` | 2026-09-25 |
| Sources | `sources-api` | `svc` | Yes | No | `sources` | Only deployment declaring a `webServices` block; `background-worker`, `availability-status-listener` do not expose one | `sources-api-go/deploy/clowdapp.yaml:178-183` | 2026-09-25 |
| Kessel Inventory | — | — | — | — | — | No known consumer currently reaches Kessel Inventory through the Clowder endpoint API (env-var `KESSEL_URL` discovery is the observed pattern instead) — nothing to record yet. When a consumer's assessment finds Kessel accessed via `get_v2_dependency_endpoint`, verify its ClowdApp and add a row here. | — | — |
| Export service | — | — | — | — | — | No known consumer inspected yet. Verify and add a row here the first time a real assessment finds an eligible Export service client. | — | — |

## Downstream auth (verified)

| Dependency | Accepts | Evidence |
|---|---|---|
| Sources | `x-rh-identity`, `x-rh-sources-psk`, certificate-based identity. Does not parse `Authorization`. | `sources-api-go` main `59837a7`, `middleware/authorization.go` and `middleware/headers.go` (2026-10-22) |

Do not infer another service's acceptance from this row. A bearer is still attached for
`authenticated: true`; see `personas/clowder-v2/migration-common.md`.

## How to use this during assessment

1. Confirm the app key from the consumer's own existing lookup (legacy `LoadedConfig.endpoints` key, or an existing
   `get_v2_dependency_endpoint`/`get_v2_private_dependency_endpoint` call) — this should match a row's App key.
2. If the row exists and isn't stale (see below), cite it directly in the packet as `Verified`, with this file plus
   the row's `Evidence` as the citation. No repo crawl, no network call.
3. If the dependency isn't in this table yet, or the consumer's usage doesn't match the row (e.g. a different
   apiPath), that's a real gap: mark `Decision required`, and prefer asking a human/the platform team over crawling
   the provider's repo. A human confirming once (or pasting one real `cdappconfig.json`) is cheaper and more durable
   than the bot re-deriving it. If the provider repo happens to already be locally available and reachable, checking
   it directly under `deploy/`, `openshift/`, or `.cicd/` is a reasonable way to answer a human's question or update
   this table — but that is a maintenance action for updating this reference, not a step in a routine consumer
   assessment.
4. Treat a row as stale — re-verify before relying on it — if it is more than ~2 quarters old, or if the target
   ticket/Jira mentions the provider recently changed its deployment topology.
5. `Public`/`Private` columns reflect whether the provider's ClowdApp declares that `webServices` block at all. If
   `Private` is "No", `get_v2_private_dependency_endpoint` will always return `None` for that dependency — use the
   public endpoint; this is not a violation of the "prefer private for in-cluster calls" default, since private
   isn't offered by the provider.
6. `apiPath` cross-checks against the path a consumer already calls (e.g. RBAC consumers should already be calling
   `/api/rbac/...`). A mismatch is a signal you may have the wrong row/dependency, not evidence to override.

## Maintenance

This file is maintained data, same as `clowder-migration.csv` — update it deliberately when a human confirms drift,
not automatically mid-assessment. When updating, always cite the provider's own `ClowdApp` template path/line and
the date verified.
