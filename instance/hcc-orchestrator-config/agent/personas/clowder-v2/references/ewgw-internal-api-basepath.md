# EWGW Internal API Base Path Convention (bundled reference)

Cached from `app-interface:docs/tenant-services/console.redhat.com/app-sops/gateway/design/ewgw-internal-api-basepath.md`
(source doc dated March 2026, ADR-080). Re-fetch the live doc when app-interface is checked out and prefer it over
this copy if they disagree — this file is a fallback for when app-interface isn't available locally.

## Decision

Standardized internal API base path: `/internal/{service}/{version}` (e.g. `/internal/sources/v2`).
`{service}` = lowercase kebab-case matching the service's public API name. `{version}` = major version, `v`-prefixed.

During migration, a service mounts the new path **alongside** its existing path; both work until all clients cut
over, then the legacy path is removed. No URL rewriting happens at the gateway — it forwards whatever base path the
service natively serves.

## Known base paths at time of caching

| Service | Internal API base path | Turnpike (public) base path |
|---|---|---|
| Export service | `/app/export/v1` | N/A |
| RBAC | `/_private/api`, `/_private/_s2s` | `/api/rbac` |
| Sources | `/internal/v2.0` (legacy), `/internal/sources/v2.0` (standard) | N/A |
| Notifications | N/A | `/api/notifications-gw/` |

Verified 2026-10-22: `sources-api-go` main registers both `/internal/{v1.0,v2.0}` and
`/internal/sources/{v1.0,v2.0}` (`routes.go:161-182`). The `/internal/sources/v2` example above
omits the `.0`; the deployed code serves `/internal/sources/v2.0`. Use the packet's exact path
and reconcile this before changing a basepath.

## How to apply this during a Clowder V2 migration

The table above describes what the *provider service* natively serves. It does **not** tell you which path a given
*consumer* should call — that depends on which Clowder-managed webService the consumer's V2 endpoint actually
resolves to. Before changing any basepath:

1. Look up the provider in `personas/clowder-v2/references/platform-dependency-v2-keys.md` and check whether it
   declares a `private` webService in addition to `public`.
2. If the provider only declares `public` (no `private` block), the consumer's only V2 endpoint is the public one —
   its native path is the existing `/api/<service>/...`-style path, **not** the `/internal/...` path from the table
   above. In that case there is no basepath migration to make; preserve the existing path append unchanged.
3. Only migrate to an `/internal/<service>/<version>` basepath when the provider's ClowdApp declares a `private`
   webService that the consumer's V2 private-endpoint lookup actually resolves to, and you have confirmed (via the
   provider's current routes, e.g. its router/handler source) that it serves that path.
4. Never infer the basepath from the table alone — always cross-check against the specific provider ClowdApp
   deployment the consumer is bound to, since one service can have multiple deployments with different exposure.

Applies only to Export service and Sources clients per the migration persona's scope gate. Do not apply basepath
changes to RBAC or Kessel.
