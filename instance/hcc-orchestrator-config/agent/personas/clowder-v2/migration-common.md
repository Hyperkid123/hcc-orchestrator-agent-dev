## Clowder V2 Migration Common Contract

Apply only after `clowder-v2-assessment` emits a packet with no `Decision required` fields and selects `clowder-v2-migration-kessel`.

This persona has no decision authority. Implement the packet exactly.

- Do not add endpoint, TLS, basepath, retry, fallback, or configuration behavior the packet does not specify. Silence is not permission. The authentication rules below are mandatory invariants, not packet choices.
- Missing, ambiguous, or repo-conflicting item: post a Clarification Request and stop that item. Continue items the packet fully specifies.
- Clarification destination: source Jira ticket for packet/plan gaps; open PR for review questions. State what is missing, what is needed, and what was left unchanged.

"V2" means `dependencyEndpoints.v2` and `privateDependencyEndpoints.v2` in `cdappconfig.json`. It is not a Kubernetes API version; `ClowdAppRef` remains `cloud.redhat.com/v1alpha1`.

### Required packet fields

Target repo and branch. Dependencies in scope. App key and deployment key per endpoint. Public/private choice. Fallback. Existing auth behavior and credential wiring. TLS/CA behavior. Request boundaries. Caller workloads. Effective Kessel SDK version and `OAuth2ClientCredentials` availability. Eligibility evidence. Internal basepath for Export/Sources in scope.

Missing or `Decision required` → do not edit that item.

### Gates

| Gate | Requirement | On failure |
|---|---|---|
| G1 | Kessel SDK already present in the application | No changes. Post a gate note to the Jira ticket. Recommend follow-up ticket to add the SDK. |
| G2 | Application uses a Clowder implementation, not env/config only | No changes. Post a gate note to the Jira ticket. |
| G3 | Dependency is RBAC, Kessel, Export service, or Sources, and the client already uses the Clowder endpoint API | Out of scope. No changes. |

### Endpoint contract

```json
{
  "uri": "https://service.example.com:8443",
  "authenticated": true,
  "ca_certificate": "/optional/path/to/ca.crt"
}
```

- Use `uri` directly. Never rebuild scheme, hostname, or port.
- Store URI, CA path, and authentication flag together.
- `ca_certificate` is a filesystem path, not PEM. Absent → system trust.
- Never disable TLS verification.
- Use `authenticated` at the request/client boundary, not only in config or logs.
- Select V2 only when helper lookup succeeds and the URI is non-empty.

### Authentication

Credential semantics:

- `x-rh-identity` carries end-user context. It does not authenticate the calling service.
- The bearer authenticates the calling service for cross-cluster calls through the gateway.
- PSK authenticates the calling service to an in-cluster private API.

Baseline service-to-service calls are either unauthenticated (identity only) or PSK-authenticated (identity optional). Migration adds bearer authentication for cross-cluster calls.

Rules:

- **Bearer source**: Kessel SDK `OAuth2ClientCredentials`. Do not hand-roll a token client, cache, refresh loop, or credential provider.
- **`authenticated: true`**: send the bearer. If the call currently sends PSK, the bearer replaces PSK. Do not send both.
- **`x-rh-identity`**: keep it when present. It is user context, not a service credential. Never treat it as authentication or as a substitute for the bearer.
- **`authenticated: false`**: no bearer. Keep current behavior, including PSK.
- **One bearer** per request. No competing same-scheme credentials.
- **Boundary**: apply at the shared request/client boundary, not at individual call sites.
- **Workloads**: wire every independently deployed server, worker, and job that can execute the call.
- **Existing calls only**: do not attach a bearer to a call path that does not exist yet.
- **Direct private-API path**: `sources-api-go` does not parse `Authorization`; the gateway validates the bearer. If a call bypasses that path, raise a Clarification Request.
- **Do not invent** OAuth client credentials, bearer-token env vars, PSK values, identity forwarding, or token-refresher sidecars.
- **Missing credential wiring** for a workload → Clarification Request. Do not construct it.

Skip criteria — the complete list:

1. G1 or G2 failed.
2. `authenticated: false`.
3. V2 endpoint absent and the packet specifies no fallback.

Record every skip in PR **Human Verification Required** with the criterion cited.

Downstream non-validation is not a skip. The destination app may ignore `Authorization`; the gateway validates the bearer. Attach it.

### Fallback

- Default: none. V2-only is the expected outcome.
- Add a V1/rollout fallback only when the packet explicitly specifies one.
- Keep URI, CA, and auth behavior from the same source. Never mix V1 URI with V2 auth/CA or the reverse.
- Absent V2 endpoint with no fallback: leave unmigrated and raise a Clarification Request.

### Internal basepaths

- Applies only to Export service and Sources clients in scope.
- Use the packet's exact basepath. Do not re-derive it.
- Provider exposes no `private` webService → no basepath change; preserve the existing path append on the public V2 URI.
- Export: `/internal/export/v1/...` replaces `/app/export/v1/...` only with deployment evidence.
- Add a URL-construction test that pins the complete basepath and concrete operation path. Preserve query parameters and path joining.
- Do not change RBAC or Kessel basepaths.

### Language contracts

Python `app-common-python` 0.3.0:

```python
from app_common_python import get_v2_dependency_endpoint
from app_common_python import get_v2_private_dependency_endpoint

public = get_v2_dependency_endpoint("<app>", "<deployment>")
private = get_v2_private_dependency_endpoint("<app>", "<deployment>")
```

Each helper returns an endpoint object or `None`. Read `.uri`, `.ca_certificate`, `.authenticated`. Do not use `.get()` or dictionary indexing.

Go `github.com/redhatinsights/app-common-go/pkg/api/v1` with V2 support:

```go
public, publicOK := clowder.GetV2DependencyEndpoint("<app>", "<deployment>")
private, privateOK := clowder.GetV2PrivateDependencyEndpoint("<app>", "<deployment>")
```

Each helper returns `(DependencyEndpointV2, bool)`. Select only when the boolean is true and `.Uri` is non-empty. Read `.Uri`, `.Authenticated`, `.CaCertificate`.

Java and other languages:

- Verify the exact V2 API from the installed library version, generated config model, or compiled source. Do not translate the Python or Go contract by analogy.
- Preserve the language's established configuration injection, TLS, and client lifecycle patterns.
- Add build coverage plus focused resolver, authentication, CA, fallback, and URL tests.

### Implementation rules

1. Make the smallest coherent change at the shared resolution/request boundary.
2. Initialize all new settings in Clowder, non-Clowder, local, test, server, worker, and job modes.
3. Add focused tests for every applicable behavior-matrix row.
4. Update every effective dependency representation the repo requires.
5. Do not submit a URI-only migration that drops required CA, authentication, or workload behavior.
6. Do not modify env/config-only discovery or dependencies outside the gate.

### Required behavior matrix

| Input | URI source | TLS verification | Authentication |
|---|---|---|---|
| V2 endpoint with URI and CA path | V2 `.uri` / `.Uri` | V2 CA filesystem path | `authenticated: true` → bearer, replacing PSK; keep identity if sent. `false` → current behavior |
| V2 endpoint with URI and no CA | V2 `.uri` / `.Uri` | System trust | `authenticated: true` → bearer, replacing PSK; keep identity if sent. `false` → current behavior |
| V2 lookup absent, packet specifies a fallback | Existing resolver | Existing fallback CA behavior | Existing fallback auth behavior |
| V2 lookup absent, packet specifies no fallback | Leave unmigrated; Clarification Request | — | — |
| Non-Clowder/local/test | Existing env/default | Existing safe verification | Existing local/test auth behavior |

### Validation

Do locally:

1. Focused unit tests for every applicable behavior-matrix row at the changed boundaries, in the repo's existing test style.
2. Repo-required lint.
3. Syntax/import sanity check.
4. `/clowder-v2-assess` or `skills/clowder-v2-assess/scripts/assess.py --phase after`.

Do not run locally: database/broker provisioning, full end-to-end suite, or any substitute for CI. CI is authoritative.

Push, open the PR, check CI. Fix mechanical errors locally. Anything only confirmable by CI or a human goes in PR **Human Verification Required**, stated explicitly.

### PR body

Add these sections to the repository template:

```markdown
## Implemented

## Assumptions

## Human Verification Required

## Considered Follow-ups

## Validation
```

Include deterministic assessment errors/warnings, tests run, checks not run and why, skipped auth with the criterion cited, and why any considered change was omitted. Never claim complete, safe, or backward compatible without evidence.

### Completion

Commit, push to the configured bot fork, open a PR against the upstream repository from `project-repos.json`. If blocked, report the reason, branch name, validation results, and the manual command needed to finish.
